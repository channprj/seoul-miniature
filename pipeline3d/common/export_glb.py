# 공개 .blend 에서 GLB(glTF 2.0 바이너리)를 낸다. 게임 엔진·웹·다른 3D 도구용이고, 재질은 근사다.
#
#   python export_glb.py quad <구역.blend> <출력.glb> [--roof-step 0.2] [--max-tex 8192]
#   python export_glb.py landmarks <출력 폴더> <여의도 구역.blend>...      # 랜드마크 하나 = GLB 하나
#
# glTF 로 옮기면서 바뀌는 것
#   - 재질: Principled BSDF 의 기본색(평색 또는 창 격자·입면 텍스처)만. 랜드마크의 툰 명암(3단 계단 음영·테두리)은 노드로 만든
#     것이라 glTF 에 옮겨지지 않는다. 텍스처 보간은 Closest → glTF 샘플러 NEAREST(픽셀 결 유지).
#   - 경복궁 기와 지붕: .blend 에서는 5–8 cm 격자 지오메트리 노드(P3D_RoofGrid)지만, GLB 에는 약 --roof-step m 격자 메시로 줄여
#     넣는다(기와 골·마루는 꼭짓점 색으로만, 색은 칸 평균). 원래 격자 그대로면 구역 하나가 수 GB 다.
#   - 지면 그림이 --max-tex px 보다 크면 줄인다(웹·엔진의 텍스처 한도).
#   - 카메라·해는 넣지 않는다. 오브젝트·장면의 사용자 속성(건물 종류 p3d_meta, 전각 자리 khs_*, 라이선스)은 extras 로 들어간다.
#   - 좌표: glTF 규약대로 +Y 위, 단위 m. 구역 GLB 는 장면 지역 좌표 그대로(원점 = 장면 원점), 랜드마크 GLB 는 원점 = 건물 바닥 중심.
import sys, os, json, math, io, tempfile, shutil
import numpy as np
import bpy
from mathutils import Matrix
from PIL import Image
Image.MAX_IMAGE_PIXELS = None   # 여의도 지면 그림은 2억 px 가 넘는다(우리가 만든 그림)

LIC = 'ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/). Geometry derived from OpenStreetMap, (c) OpenStreetMap contributors. Seoul Miniature by midagedev.'
TMP = tempfile.mkdtemp(prefix='glb_'); import atexit; atexit.register(lambda: shutil.rmtree(TMP, ignore_errors=True))

def opt(a, k, d=None):
    if k not in a: return d
    i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v

def _lin(c):
    c = np.asarray(c, np.float32); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def materials_for_gltf():
    for m in bpy.data.materials:
        if not m.node_tree: continue
        N, L = m.node_tree.nodes, m.node_tree.links
        pb = next((n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None); out = next((n for n in N if n.bl_idname == 'ShaderNodeOutputMaterial'), None)
        if pb is None or out is None: continue
        for n in list(N):  # 지붕 꼭짓점 색: Attribute('col') → Color Attribute 노드(내보내기가 COLOR_0 으로 알아본다)
            if n.bl_idname == 'ShaderNodeAttribute' and n.attribute_name == 'col':
                vc = N.new('ShaderNodeVertexColor'); vc.layer_name = 'col'
                for l in list(n.outputs['Color'].links): L.new(vc.outputs['Color'], l.to_socket)
                N.remove(n)
        for l in list(out.inputs['Surface'].links): L.remove(l)
        L.new(pb.outputs[0], out.inputs['Surface'])   # 툰 혼합 셰이더를 건너뛰고 Principled 만
        for n in N:
            if n.bl_idname == 'ShaderNodeTexImage': n.interpolation = 'Closest'

def shrink_textures(maxpx):
    for img in list(bpy.data.images):
        if img.source != 'FILE' or max(img.size) <= maxpx or not img.packed_file: continue
        im = Image.open(io.BytesIO(img.packed_file.data)); f = maxpx / max(im.size)
        im = im.resize((max(1, round(im.size[0] * f)), max(1, round(im.size[1] * f))), Image.LANCZOS)
        p = os.path.join(TMP, os.path.basename(img.filepath_raw) or (img.name + '.png')); im.save(p)
        new = bpy.data.images.load(p); new.pack(); new.filepath_raw = img.filepath_raw; new.name = img.name + '_glb'
        img.user_remap(new); print('texture', img.name, img.size[:], '->', new.size[:], flush=True)

def roofs_to_meshes(step):
    """P3D_RoofGrid 지오메트리 노드 지붕 → 약 step m 격자의 보통 메시(꼭짓점 색 'col', 선형)."""
    from scipy.ndimage import uniform_filter
    n_obj = n_v = 0
    for o in list(bpy.data.objects):
        md = o.modifiers.get('RoofGrid') if o.type == 'MESH' else None
        if md is None: continue
        ng = md.node_group; v = {it.name: md[it.identifier] for it in ng.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT' and it.identifier in md}
        NX, NY, G = int(v['NX']), int(v['NY']), float(v['G'])
        def px(img):
            n = img.channels; buf = np.empty(NX * NY * n, np.float32); img.pixels.foreach_get(buf); return buf.reshape(NY, NX, n)
        H = px(v['Height'])[..., 0]; C = px(v['Color'])
        ins = C[..., 3] > 0.5; k = max(1, int(round(step / G)))
        w = uniform_filter(ins.astype(np.float32), k, mode='nearest')
        cs = np.stack([uniform_filter(np.where(ins, C[..., c], 0), k, mode='nearest') for c in range(3)], -1) / np.maximum(w, 1e-6)[..., None]
        jj, ii = np.arange(0, NY, k), np.arange(0, NX, k)
        if ii[-1] != NX - 1: ii = np.append(ii, NX - 1)
        if jj[-1] != NY - 1: jj = np.append(jj, NY - 1)
        sub = ins[np.ix_(jj, ii)]
        if sub.sum() < 4: continue
        X = float(v['X0']) + ii * G; Y = float(v['Y0']) + jj * G; Z = float(v['Z0']) + H[np.ix_(jj, ii)] * float(v['ZS'])
        idx = -np.ones(sub.shape, np.int64); idx[sub] = np.arange(sub.sum())
        gx, gy = np.meshgrid(X, Y); V = np.stack([gx[sub], gy[sub], Z[sub]], 1)
        a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]; ok = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
        F = np.stack([a[ok], b[ok], c[ok], d[ok]], 1)
        me = bpy.data.meshes.new(o.name + '_glb'); me.from_pydata(V.tolist(), [], F.tolist()); me.materials.append(v['Material'])
        col = np.concatenate([_lin(cs[np.ix_(jj, ii)][sub]), np.ones((len(V), 1), np.float32)], 1)
        ca = me.color_attributes.new('col', 'FLOAT_COLOR', 'POINT'); ca.data.foreach_set('color', col.ravel()); me.color_attributes.active_color = ca
        me.shade_smooth()   # 높이장이라 부드러운 음영이 자연스럽고, 면마다 꼭짓점이 나뉘지 않아 GLB 가 4배 가볍다
        me.update(); o.modifiers.remove(md); o.data = me; n_obj += 1; n_v += len(V)
    print('roofs', n_obj, 'verts', n_v, 'step', step, flush=True)

def export(path, selection=False):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=selection, export_apply=True, export_extras=True,
                              export_cameras=False, export_lights=False, export_yup=True, export_draco_mesh_compression_enable=False,
                              export_vertex_color='MATERIAL', export_image_format='AUTO')
    print('glb', path, os.path.getsize(path), flush=True)

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
STEP = float(opt(a, '--roof-step', 0.2)); MAXT = int(opt(a, '--max-tex', 8192)); mode = a[0]

if mode == 'quad':
    src, out = a[1], a[2]
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene; sc['p3d_glb_note'] = 'glTF export: base colour and textures only (toon shading not included); roofs resampled to ~%.2f m grid' % STEP
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT'): bpy.data.objects.remove(o)
    roofs_to_meshes(STEP); materials_for_gltf(); shrink_textures(MAXT)
    export(out)

elif mode == 'landmarks':
    outd, srcs = a[1], a[2:]
    # 종류(scene p3d_meta) → 파일 이름. 여러 동·부속은 한 파일로.
    GROUP = {'63': '63_building', '63_podium': '63_building', 'parc1': 'parc_one', 'parc2': 'parc_one', 'ifc1': 'ifc_seoul', 'ifc2': 'ifc_seoul', 'ifc3': 'ifc_seoul',
             'ifc_gate': 'ifc_seoul', 'conrad': 'conrad_seoul', 'hyundai': 'the_hyundai_seoul', 'lg': 'lg_twin_towers', 'fki': 'fki_tower', 'fki_hall': 'fki_tower',
             'anchor': 'anchor_one', 'post': 'yeouido_post_tower', 'assembly': 'national_assembly', 'church': 'yoido_full_gospel_church',
             'KRX한국거래소서울사무소': 'krx_seoul_office', '국회도서관': 'national_assembly_library', '국회박물관': 'national_assembly_museum',
             '국회소통관': 'national_assembly_communication_hall', '국회의원회관': 'national_assembly_members_office', '국회의정관': 'national_assembly_uijeonggwan'}
    BYNAME = {'b14582': 'kbs_main', 'b14584': 'kbs_main', 'b14327': 'kbs_annex'}   # KBS 신관·별관(종류는 lowrise, 재질만 사진 대조)
    TITLE = {'63_building': '63빌딩', 'parc_one': '파크원(타워1·NH금융타워)', 'ifc_seoul': 'IFC 서울(One·Two·Three IFC, 몰 입구)', 'conrad_seoul': '콘래드 서울',
             'the_hyundai_seoul': '더현대 서울', 'lg_twin_towers': 'LG트윈타워', 'fki_tower': 'FKI타워(전경련회관)와 컨퍼런스센터', 'anchor_one': '앵커원',
             'yeouido_post_tower': '여의도우체국', 'national_assembly': '국회의사당', 'yoido_full_gospel_church': '여의도순복음교회', 'krx_seoul_office': '한국거래소 서울사무소',
             'national_assembly_library': '국회도서관', 'national_assembly_museum': '국회박물관', 'national_assembly_communication_hall': '국회소통관',
             'national_assembly_members_office': '국회의원회관', 'national_assembly_uijeonggwan': '국회의정관', 'kbs_main': 'KBS 신관', 'kbs_annex': 'KBS 별관'}
    want = {}   # 오브젝트 이름 → (그룹, 원본 파일)
    for f in srcs:
        bpy.ops.wm.open_mainfile(filepath=f); meta = json.loads(bpy.context.scene['p3d_meta'])
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.name in want: continue
            k = meta.get(str(o.pass_index), ''); g = BYNAME.get(o.name) or (GROUP.get(k[9:]) if k.startswith('landmark:') else None)
            if g: want[o.name] = (g, f)
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
    for f in srcs:
        names = [n for n, (g, ff) in want.items() if ff == f]
        if not names: continue
        with bpy.data.libraries.load(f, link=False) as (s_, d_): d_.objects = names
        for o in d_.objects:
            if o is not None: sc.collection.objects.link(o); o['landmark'] = want[o.name][0]
    materials_for_gltf()
    groups = {}
    for o in sc.objects: groups.setdefault(o['landmark'], []).append(o)
    rows = []
    for g, objs in sorted(groups.items()):
        P = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in objs])
        off = np.array([(P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2, P[:, 2].min()])
        T = Matrix.Translation(tuple(-off)); keep = {o: o.matrix_world.copy() for o in objs}
        for o in objs:
            o.matrix_world = T @ o.matrix_world; o['title'] = TITLE.get(g, g); o['license'] = LIC
            o['scene_offset_m'] = [round(float(x), 3) for x in off]   # 장면 지역 좌표에서 이만큼 옮김(원래 자리 = 이 값 더하기)
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs: o.select_set(True)
        p = os.path.join(outd, 'yeouido_%s.glb' % g); export(p, selection=True)
        rows.append(dict(file=os.path.basename(p), title=TITLE.get(g, g), objects=len(objs), verts=int(len(P)), size_m=[round(float(x), 1) for x in (P.max(0) - P.min(0))], bytes=os.path.getsize(p)))
        for o, m in keep.items(): o.matrix_world = m
    json.dump(rows, open(os.path.join(outd, 'landmarks.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(rows, ensure_ascii=False), flush=True)
