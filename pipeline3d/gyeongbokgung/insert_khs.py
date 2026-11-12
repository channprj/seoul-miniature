# 공개 경복궁 .blend 의 전각 자리(KHS_SLOTS)에, 각자 국가유산청에서 받은 3D 모델을 끼운다. 대체 모형(KHS_STANDIN/<자리>)은 지운다.
#
#   python insert_khs.py <공개.blend> <국가유산청 폴더> <출력.blend> [--only slot3001,gwanghwamun] [--work <풀 폴더>] [--pack] [--list]
#
#   <국가유산청 폴더>: 국가유산청 디지털 서비스(digital.khs.go.kr)의 「경복궁 3D 기록」에서 받은 zip 을 그대로 두거나 푼 폴더.
#     - 전각: 자리 빈 오브젝트의 khs_model 속성과 같은 이름의 zip(예: 국보_경복궁_경회루.zip) 또는 같은 이름의 폴더(안에 .fbx).
#     - 광화문: 폴더 어딘가의 SM_GwanghwamunComplex.fbx(광화문·월대·해태 일원 기록).
#   --list  : 이 파일의 자리와 찾은 원본만 보여 주고 끝낸다.
#   --work  : zip 을 풀 폴더(기본 <출력>_khs/). 텍스처는 이 폴더를 가리키므로 출력 .blend 와 함께 둔다.
#   --pack  : 텍스처를 .blend 안에 넣는다. 그러면 출력 파일에 국가유산청 자료가 들어가므로 다른 곳에 올리지 마세요.
#
# 모델 → 지도 변환은 렌더에 쓴 것과 같다(gen.py khs_place): FBX 의 객체 변환을 메시에 굽고, 떠돌이 객체를 빼고,
# 크기가 400 m 를 넘으면 cm 단위로 보고 0.01 배, 지면 재질(ground·grass·road …) 면은 지면 ID(1)로 나눈 뒤
# 지도 xy = R(theta)·모델 xy + (tx, ty), z = 모델 z + tz.
# 출처 표시: 국가유산청(공공누리 제1유형). 출력 .blend 는 원본을 담으므로 재배포하지 마세요(각자 받게 하세요).
import sys, os, json, math, zipfile, glob
import numpy as np
import bpy
from mathutils import Matrix

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
def opt(k, d=None, flag=False):
    if k not in a: return d
    i = a.index(k)
    if flag: del a[i]; return True
    v = a[i + 1]; del a[i:i + 2]; return v
ONLY = set((opt('--only') or '').split(',')) - {''}; WORK = opt('--work'); PACK = opt('--pack', False, True); LIST = opt('--list', False, True)
SRC, KDIR, OUT = os.path.abspath(a[0]), os.path.abspath(a[1]), os.path.abspath(a[2]) if len(a) > 2 else None
WORK = os.path.abspath(WORK or (os.path.splitext(OUT)[0] + '_khs' if OUT else os.path.join(KDIR, '_work')))
GROUND_KEYS = ('ground', 'grass', 'lawn', 'road', 'terrain', 'soil', 'dirt', 'landscape', 'gravel', 'sand')

bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
scol = bpy.data.collections.get('KHS_SLOTS')
slots = sorted(scol.objects, key=lambda o: o.name) if scol else []
if not slots: sys.exit('이 파일에는 전각 자리(KHS_SLOTS)가 없습니다.')

def find_src(e):
    if e.name == 'gwanghwamun':
        hit = glob.glob(os.path.join(KDIR, '**', 'SM_GwanghwamunComplex.fbx'), recursive=True)
        return hit[0] if hit else None
    nm = e['khs_model']
    for p in (os.path.join(KDIR, nm + '.zip'), os.path.join(KDIR, nm)):
        if os.path.exists(p): return p
    hit = glob.glob(os.path.join(KDIR, '**', nm + '.zip'), recursive=True) + glob.glob(os.path.join(KDIR, '**', nm), recursive=True)
    return hit[0] if hit else None

plan = [(e, find_src(e)) for e in slots if not ONLY or e.name in ONLY]
for e, p in plan:
    print('%-12s %-40s %s' % (e.name, e.get('khs_model', ''), p or '(못 찾음 — 대체 모형 그대로)'), flush=True)
if LIST or not OUT: sys.exit(0)

def unpack(p, name):
    """zip 이면 WORK/<name>/ 에 풀고 그 폴더를, 폴더면 그대로 돌려준다."""
    if os.path.isdir(p): return p
    d = os.path.join(WORK, name); os.makedirs(d, exist_ok=True)
    with zipfile.ZipFile(p) as z:
        for it in z.infolist():
            if it.is_dir(): continue
            dst = os.path.join(d, os.path.basename(it.filename))
            if not os.path.exists(dst) or os.path.getsize(dst) != it.file_size: open(dst, 'wb').write(z.read(it))
    return d

IMG_EXT = ('.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.bmp')
_SHARED = None
def shared_index():
    """폴더 전체(풀린 파일과 zip 안)의 그림 이름 → 위치. 전각 zip 밖에 있는 공용 텍스처(예: T_KoreanTile_BC)를 다른 전각 자료에서 빌려 오는 데 쓴다."""
    global _SHARED
    if _SHARED is None:
        _SHARED = {}
        for t in glob.glob(os.path.join(KDIR, '**', '*.*'), recursive=True):
            if t.lower().endswith(IMG_EXT): _SHARED.setdefault(os.path.splitext(os.path.basename(t))[0].lower(), ('file', t))
            elif t.lower().endswith('.zip'):
                try:
                    for n in zipfile.ZipFile(t).namelist():
                        if n.lower().endswith(IMG_EXT): _SHARED.setdefault(os.path.splitext(os.path.basename(n))[0].lower(), ('zip', t, n))
                except zipfile.BadZipFile: pass
    return _SHARED

def fetch_shared(st):
    hit = shared_index().get(st)
    if not hit: return None
    if hit[0] == 'file': return hit[1]
    d = os.path.join(WORK, '_shared'); os.makedirs(d, exist_ok=True); dst = os.path.join(d, os.path.basename(hit[2]))
    if not os.path.exists(dst): open(dst, 'wb').write(zipfile.ZipFile(hit[1]).read(hit[2]))
    return dst

def is_normal(fn): return any(k in os.path.basename(fn).upper() for k in ('_NM', '_N.', '_NRM', '_NORMAL'))

def fix_normal(p):
    """일부 노멀맵은 B 채널이 0 인 2채널(X, Y) 형식이라 Blender 가 Z = -1 로 읽어 면이 검게 나온다. Z 를 복원한 사본을 WORK 에 쓴다(받은 원본은 그대로)."""
    from PIL import Image
    im = Image.open(p); a = np.asarray(im.convert('RGBA')).astype(np.float32)
    if a[..., 2].mean() > 40: return p
    x = a[..., 0] / 127.5 - 1; y = a[..., 1] / 127.5 - 1; z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
    a[..., 2] = np.round((z + 1) * 127.5)
    d = os.path.join(WORK, '_fixed'); os.makedirs(d, exist_ok=True); dst = os.path.join(d, os.path.splitext(os.path.basename(p))[0] + '.png')
    Image.fromarray(a.astype(np.uint8), 'RGBA').save(dst); return dst

def import_fbx(folder):
    before = set(bpy.data.objects); imgs0 = set(bpy.data.images)
    import addon_utils; addon_utils.enable('io_scene_fbx')
    for f in sorted(glob.glob(os.path.join(folder, '*.fbx')) + glob.glob(os.path.join(folder, '*.FBX'))):
        try: bpy.ops.import_scene.fbx(filepath=f, use_anim=False)
        except RuntimeError:  # Blender 가 못 읽는 ASCII FBX: FBX2glTF 등으로 <이름>_conv.glb 를 만들어 같은 폴더에 두면 그것을 읽는다
            g = os.path.splitext(f)[0] + '_conv.glb'
            if not os.path.exists(g): raise
            bpy.ops.import_scene.gltf(filepath=g)
    tex = {os.path.splitext(os.path.basename(t))[0].lower(): t for t in glob.glob(os.path.join(folder, '**', '*.*'), recursive=True) if t.lower().endswith(IMG_EXT)}
    # 렌더 캐시(khs_cache)와 같은 텍스처 정리: FBX 안 경로는 만든 사람 장비 경로라 이름으로 다시 찾고, 없으면 다른 전각 자료에서 빌리고,
    # 끝내 없으면 노드 연결을 끊어 재질 기본값으로 둔다(자홍색 방지). 노멀맵은 2채널 형식을 고친다.
    gone = set(); nb = 0
    for img in set(bpy.data.images) - imgs0:
        if img.source != 'FILE': continue
        fn = os.path.basename(img.filepath or img.name); st = os.path.splitext(fn)[0].lower()
        c = tex.get(st) or tex.get(st.split('.')[0])
        if not c: c = fetch_shared(st) or fetch_shared(st.split('.')[0]); nb += bool(c)
        if not c:
            if not img.packed_file: gone.add(img)
            continue
        if img.packed_file:
            try: img.unpack(method='REMOVE')
            except Exception: pass
        img.filepath = fix_normal(c) if is_normal(c) else c; img.reload()
    for m in bpy.data.materials:
        if not m.node_tree: continue
        for nd in list(m.node_tree.nodes):
            if getattr(nd, 'image', None) in gone:
                for o_ in nd.outputs:
                    for l in list(o_.links): m.node_tree.links.remove(l)
                nd.image = None
    for i in gone: bpy.data.images.remove(i)
    if nb or gone: print('  textures borrowed', nb, 'missing', len(gone), flush=True)
    return [o for o in bpy.data.objects if o not in before]

def as_cache(new):
    """khs_cache.py 와 같은 정리: 변환 굽기 → 떠돌이 제거 → 단위 → 지면 재질 분리. (건물 객체들, 지면 객체들)"""
    meshes = [o for o in new if o.type == 'MESH']
    for o in meshes:
        if o.data.users > 1: o.data = o.data.copy()
        o.data.transform(o.matrix_world); o.parent = None; o.matrix_world = Matrix.Identity(4)
    for o in [o for o in new if o.type != 'MESH']: bpy.data.objects.remove(o)
    info = []
    for o in meshes:
        v = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get('co', v); v = v.reshape(-1, 3)
        info.append((o, v.min(0), v.max(0), len(v)))
    allv = np.concatenate([np.array([i[1], i[2]]) for i in info]); W = np.repeat([i[3] for i in info], 2)
    med = np.array([np.median(np.repeat(allv[:, k], np.minimum(W, 50))) for k in range(3)])
    cen = np.array([(i[1] + i[2]) / 2 for i in info]); dist = np.linalg.norm((cen - med)[:, :2], axis=1)
    R = np.percentile(np.repeat(dist, np.minimum([i[3] for i in info], 50)), 95)
    keep = []
    for (o, mn, mx, nv), dd in zip(info, dist):
        if dd > 3 * R + 15: bpy.data.objects.remove(o)
        else: keep.append((o, mn, mx))
    mn = np.min([k[1] for k in keep], 0); mx = np.max([k[2] for k in keep], 0)
    if (mx - mn).max() > 400:
        for o, _, _ in keep: o.data.transform(Matrix.Diagonal((0.01, 0.01, 0.01, 1.0)))
    meshes = [k[0] for k in keep]
    gmat = {m.name for o in meshes for m in o.data.materials if m and any(k in m.name.lower() for k in GROUND_KEYS)}
    for o in list(meshes):
        idx = [i for i, m in enumerate(o.data.materials) if m and m.name in gmat]
        if not idx or len(idx) == len(o.data.materials): continue
        before = set(bpy.data.objects)
        bpy.ops.object.select_all(action='DESELECT'); bpy.context.view_layer.objects.active = o; o.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT')
        for i in idx: o.active_material_index = i; bpy.ops.object.material_slot_select()
        bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        meshes += [x for x in bpy.data.objects if x not in before]
    G, B = [], []
    for o in meshes:
        if len(o.data.polygons) == 0: bpy.data.objects.remove(o); continue
        ms = {m.name for m in o.data.materials if m}
        (G if ms and ms <= gmat else B).append(o)
    return B, G

def lin(hexs):
    h = hexs.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]

done = []
for e, p in plan:
    if not p: continue
    col = bpy.data.collections.new('KHS_' + e.name); sc.collection.children.link(col)
    rt = bpy.data.objects.new('KHSR_' + e.name, None); col.objects.link(rt)
    folder = os.path.dirname(p) if p.lower().endswith('.fbx') else unpack(p, e['khs_model'])
    new = import_fbx(folder)
    if e.name == 'gwanghwamun':  # gen.py 의 광화문 판: 계층 그대로, 지면 재질 몇 개는 평색
        for m_ in bpy.data.materials:
            if not m_.name.startswith('M_GHM') or not m_.use_nodes: continue
            bs = [n_ for n_ in m_.node_tree.nodes if n_.type == 'BSDF_PRINCIPLED']
            flat = {'M_GHM_Grass': '#5fb043', 'M_GHM_Ground02A1': '#d8ccb2', 'M_GHM_Ground01A': '#d4c7aa', 'M_GHM_Road': '#cdbfa4'}.get(m_.name)
            if bs and flat:
                inp = bs[0].inputs['Base Color']
                for l_ in list(inp.links): m_.node_tree.links.remove(l_)
                inp.default_value = lin(flat)
        for o in new:
            for c_ in list(o.users_collection): c_.objects.unlink(o)
            col.objects.link(o)
            if o.parent is None: o.parent = rt
            if o.type == 'MESH': o.pass_index = 1 if 'Ground' in o.name else 2
        rt.rotation_euler = (0, 0, math.radians(e['theta'])); rt.location = (e['tx'], e['ty'], 0.03)
    else:
        B, G = as_cache(new)
        for o in B + G:
            for c_ in list(o.users_collection): c_.objects.unlink(o)
            col.objects.link(o); o.parent = rt; o.pass_index = 1 if o in G else int(e['pass_index'])
        rt.rotation_euler = (0, 0, math.radians(e['theta'])); rt.location = (e['tx'], e['ty'], e.get('tz', 0.0))
    sb = bpy.data.collections.get(e.name)  # 대체 모형 지우기
    nrm = 0
    if sb:
        for o in list(sb.objects): bpy.data.objects.remove(o); nrm += 1
        bpy.data.collections.remove(sb)
    e['inserted'] = True; done.append(e.name)
    print('inserted', e.name, 'removed stand-in objects', nrm, flush=True)
if PACK:
    for img in bpy.data.images:
        if img.source == 'FILE' and not img.packed_file and os.path.exists(bpy.path.abspath(img.filepath)): img.pack()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True)
print('saved', OUT, 'slots', len(done), done, flush=True)
