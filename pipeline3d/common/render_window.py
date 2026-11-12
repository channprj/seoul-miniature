# 공개 .blend 를 열어 지도의 한 창(예: 8×8 타일 하나)만 렌더한다. 카메라 방향·해·재질은 파일 그대로이고 위치·크기만 옮긴다.
#   python render_window.py <장면.blend> <x0> <y0> <w> <h> <출력.png> [--id] [--spp N] [--threads N] [--roof-step N]
#   x0,y0,w,h = 그 지도 전체 조건 렌더(cond.png)의 화소 좌표. 경복궁 22016×13568(6.25 cm/px), 여의도 22016×13568(12.5 cm/px).
#   예) 경복궁 타일 (i,j) = x0 i·2752, y0 j·1696, 2752×1696 / 여의도 타일 (i,j) = x0 i·2752, y0 j·1696, 2752×1696.
#   --id: 같은 창의 ID 패스(<출력>_id.png, R·256+G = pass_index)와 대체 모형 목록(<출력>_slots.json)도 낸다.
# 파일을 열자마자 렌더하면(이 스크립트 없이 F12) 그 파일이 맡은 구역 전체가 공개판 조건 렌더와 같은 크기·해상도로 나온다.
import sys, json, math, os
import bpy

a = sys.argv[1:]
def opt(k, d=None, flag=False):
    if k not in a: return d
    i = a.index(k)
    if flag: del a[i]; return True
    v = a[i + 1]; del a[i:i + 2]; return v
WANT_ID = opt('--id', False, True); SPP = opt('--spp'); THR = opt('--threads'); RSTEP = opt('--roof-step')
path, x0, y0, w, h, out = a[0], float(a[1]), float(a[2]), int(a[3]), int(a[4]), a[5]
bpy.ops.wm.open_mainfile(filepath=path)
sc = bpy.context.scene; px = float(sc['p3d_px_m'])
if sc['p3d_map'] == 'yeouido':
    k = px / 0.0625; wx0, wy0, wx1, wy1 = json.loads(sc['p3d_window_6p25']); qx, qy = wx0 / k, wy0 / k; qw, qh = json.loads(sc['p3d_render_px'])
else:
    qx, qy, qw, qh = json.loads(sc['p3d_window_px'])
cam = sc.camera; M = cam.matrix_world.to_3x3(); right, up = M.col[0], M.col[1]
dx = (x0 + w / 2) - (qx + qw / 2); dy = (y0 + h / 2) - (qy + qh / 2)
cam.location = cam.location + right * (dx * px) - up * (dy * px)
cam.data.ortho_scale = max(w, h) * px
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
if SPP: sc.cycles.samples = int(SPP)
if THR: sc.render.threads_mode = 'FIXED'; sc.render.threads = int(THR)
if RSTEP and 'P3D_RoofGrid' in bpy.data.node_groups:   # 경복궁 기와 지붕 격자를 N 칸씩 건너뛰어 메모리를 줄인다(1 = 원래 격자)
    bpy.data.node_groups['P3D_RoofGrid'].nodes['Step'].integer = int(RSTEP)
sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = os.path.abspath(out)
bpy.ops.render.render(write_still=True)
if WANT_ID:
    mt = bpy.data.materials.new('id'); mt.use_nodes = True; nt = mt.node_tree; nt.nodes.clear()
    o_ = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(em.outputs[0], o_.inputs[0])
    v = nt.nodes.new('ShaderNodeObjectInfo').outputs['Object Index']
    def mn(op, x, y):
        n_ = nt.nodes.new('ShaderNodeMath'); n_.operation = op
        for i_, s_ in enumerate((x, y)):
            if s_ is None: continue
            if isinstance(s_, (int, float)): n_.inputs[i_].default_value = s_
            else: nt.links.new(s_, n_.inputs[i_])
        return n_.outputs[0]
    hi = mn('FLOOR', mn('DIVIDE', v, 256.0), None); lo = mn('SUBTRACT', v, mn('MULTIPLY', hi, 256.0))
    cmb = nt.nodes.new('ShaderNodeCombineColor'); nt.links.new(mn('DIVIDE', hi, 255.0), cmb.inputs[0]); nt.links.new(mn('DIVIDE', lo, 255.0), cmb.inputs[1]); cmb.inputs[2].default_value = 0
    nt.links.new(cmb.outputs[0], em.inputs[0])
    sc.cycles.samples = 1; sc.cycles.filter_width = 0.01; sc.view_settings.view_transform = 'Raw'; sc.cycles.max_bounces = 0; sc.render.dither_intensity = 0.0
    if sc.world: sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.0
    for ob in sc.objects:
        if ob.type == 'LIGHT': ob.hide_render = True
    sc.view_layers[0].material_override = mt; base = os.path.splitext(os.path.abspath(out))[0]
    sc.render.filepath = base + '_id.png'; bpy.ops.render.render(write_still=True)
    sl = {}
    for ob in bpy.data.objects:
        if 'khs_slot' in ob: sl.setdefault(ob['khs_slot'], []).append(ob.pass_index)
    json.dump(sl, open(base + '_slots.json', 'w'))
print('done', out, flush=True)
