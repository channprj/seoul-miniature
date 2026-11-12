# GLB 를 Blender 로 다시 불러와 한 장 렌더한다(내보낸 파일이 열리고 모양·색이 맞는지 보는 용도).
#   python view_glb.py <x.glb> <out.png> [front|oblique] [--px 900] [--spp 32]
#   front = 남쪽(-Y)에서 정면, oblique = 공개판과 비슷한 35° 내려다보기. 정사투영, 해 하나 + 흰 하늘빛.
import sys, math, os
import numpy as np
import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
def opt(k, d):
    if k not in a: return d
    i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
PX = int(opt('--px', 900)); SPP = int(opt('--spp', 32)); THR = int(opt('--threads', 8))
src, out = a[0], a[1]; mode = a[2] if len(a) > 2 else 'front'
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=src)
P = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in sc.objects if o.type == 'MESH' and len(o.data.vertices)])
lo, hi = P.min(0), P.max(0); c = (lo + hi) / 2; ext = hi - lo
cd = bpy.data.cameras.new('cam'); cd.type = 'ORTHO'; cd.clip_start = 0.1; cd.clip_end = 1e5
co = bpy.data.objects.new('cam', cd); sc.collection.objects.link(co); sc.camera = co
if mode == 'front':
    co.rotation_euler = (math.radians(90), 0, 0); co.location = (c[0], lo[1] - 2000, c[2]); cd.ortho_scale = max(ext[0], ext[2]) * 1.12
    w, h = (PX, max(64, int(PX * ext[2] / max(ext[0], 1e-3)))) if ext[0] >= ext[2] else (max(64, int(PX * ext[0] / max(ext[2], 1e-3))), PX)
else:
    co.rotation_euler = (math.radians(55), 0, math.radians(45)); d = co.rotation_euler.to_matrix() @ Vector((0, 0, 1)); co.location = Vector(tuple(c)) + d * 3000
    cd.ortho_scale = float(np.hypot(ext[0], ext[1])) * 0.8; w, h = PX, int(PX * 0.62)
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 3.6; sd.angle = math.radians(1.5)
so = bpy.data.objects.new('sun', sd); so.rotation_euler = (math.radians(50), 0, math.radians(-28)); sc.collection.objects.link(so)
wo = bpy.data.worlds.new('w'); wo.use_nodes = True; wo.node_tree.nodes['Background'].inputs[0].default_value = (1, 1, 1, 1); wo.node_tree.nodes['Background'].inputs[1].default_value = 0.7; sc.world = wo
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.use_denoising = False
sc.render.threads_mode = 'FIXED'; sc.render.threads = THR
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
sc.view_settings.view_transform = 'Standard'; sc.render.film_transparent = False; sc.render.filepath = os.path.abspath(out)
from bpy_extras.object_utils import world_to_camera_view
bpy.context.view_layer.update()
print('cam', [tuple(round(x, 3) for x in world_to_camera_view(sc, co, Vector(tuple(p_)))) for p_ in (lo, c, hi)], flush=True)
bpy.ops.render.render(write_still=True)
print('view', src, 'meshes', sum(1 for o in sc.objects if o.type == 'MESH'), 'verts', len(P), 'size_m', ext.round(1).tolist(), flush=True)
