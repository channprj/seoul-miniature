# 파일럿: OSM/V-World 파생 풋프린트로 세부(기와 줄, 창, 옥상 설비)를 가진 새 장면을 만들어 같은 카메라로 렌더.
#   venv/bin/python gen.py <win_x> <win_y> <out_prefix> [--save-blend <경로.blend>] [--no-render]
#   --save-blend: 세운 장면(카메라·해·재질·텍스처 포함)을 렌더 직전 상태로 저장한다(common/blend_save.py). --no-render: 저장만 하고 끝낸다.
#   공개 장면(국가유산청 모델 없음)은 P3D_KHS·P3D_KHSP 를 비우고 P3D_KHS_SLOTS(전각 배치 json)·P3D_KHS_GEO(광화문 정합 json)를 주면
#   전각 자리에 OSM 대체 모형을 세우고 그 오브젝트를 컬렉션 KHS_STANDIN/slot<번호> 에, 자리 표시 빈 오브젝트를 KHS_SLOTS 에 둔다.
# 원본 .blend / KHS 텍스처는 쓰지 않는다. 텍스처는 여기서 PIL 로 직접 만든다.
import sys, json, math, random, os
import numpy as np
import bpy
from mathutils import Vector
from PIL import Image, ImageDraw
import shapely
from shapely.geometry import Polygon, Point
from shapely.geometry.polygon import orient

ROOT = os.environ.get('P3D_ROOT', 'work/')  # 입력 폴더(pipeline3d/README.md 의 "입력")
R = ROOT + 'redraw/'
HERE = os.path.dirname(os.path.abspath(__file__))
GV2 = os.environ.get('P3D_GROUND', '') == 'v2'  # 3차(연못 지형): 바닥 그림 ground_clean_v2.png·나무 trees_px_v2.json(ground_patch.py) + KHS 배치의 'bridges'(경회루 돌다리). 없으면 기존과 같음.
import tempfile, atexit, shutil; TEXD = tempfile.mkdtemp(prefix='p3dtex_'); atexit.register(lambda: shutil.rmtree(TEXD, ignore_errors=True))  # 프로세스별 텍스처 폴더(병렬 쓰기 경합 방지)
SAVE_BLEND, NO_RENDER = None, False
if '--save-blend' in sys.argv: _i = sys.argv.index('--save-blend'); SAVE_BLEND = sys.argv[_i + 1]; del sys.argv[_i:_i + 2]
if '--no-render' in sys.argv: sys.argv.remove('--no-render'); NO_RENDER = True
X0, Y0, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
if SAVE_BLEND: sys.path.insert(0, os.path.join(HERE, '..', 'common')); import roofgrid
WW, WH = int(os.environ.get('P3D_W', 1408)), int(os.environ.get('P3D_H', 1024))
PX, W, H = 0.0625, 22016, 13568
cam = json.load(open(R + 'hires/camera/nw45w_x8_0p0625_camera.json'))
EX, EY, VD = (np.array(cam[k]) for k in ('screen_x_axis', 'screen_y_axis', 'view_dir'))
CX, CY, CL = cam['cx'], cam['cy'], np.array(cam['cam_location'])

def proj(p):
    p = np.asarray(p, float)
    return (p @ EX - CX) / PX + W / 2, H / 2 - (p @ EY - CY) / PX

def lin(hexs):
    h = hexs.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]

# ---------- 텍스처 ----------
PPM = 32
BAY, FLH = 3.2, 3.2
FAC = {  # 벽, 벽 어두운 줄, 창틀, 유리, 유리 밝은 면
    'brick_red': ('#b4553c', '#964431', '#e8dcc8', '#27333f', '#3f5567', True),
    'brick_brown': ('#8c5a44', '#744838', '#d9cdb8', '#27333f', '#3f5567', True),
    'brick_beige': ('#c9a988', '#b29272', '#f1e9d8', '#2b3a47', '#46627a', True),
    'stucco_white': ('#ece6d6', '#d8d0bd', '#8e8a80', '#2b3a47', '#46627a', False),
    'stucco_cream': ('#e6d3aa', '#d2bd92', '#f5eedc', '#2b3a47', '#46627a', False),
    'stucco_grey': ('#b9b8b2', '#a3a29c', '#e6e4dc', '#27333f', '#3f5567', False),
    'stucco_sand': ('#d6bf9a', '#c1a982', '#f2e8d2', '#2b3a47', '#46627a', False),
    'office_beige': ('#cdbfa6', '#b6a78d', '#eee6d4', '#22303c', '#3a5873', False),
    'office_grey': ('#a9adb0', '#92969a', '#dcdfe0', '#22303c', '#3a5873', False),
    'civic': ('#c8c2b4', '#b0aa9c', '#ebe7dc', '#22303c', '#3a5873', False),
    'resi': ('#dcd6c8', '#c6c0b2', '#f2efe6', '#2b3a47', '#46627a', False),
    'glass_blue': ('#5d7f9c', '#4b6a85', '#c9d6de', '#2f4a63', '#4f7696', False),
    'glass_teal': ('#5b8f8f', '#4a7878', '#c9dedc', '#2f5a5d', '#4f8a8c', False),
    'hanok': ('#efe8d6', '#d9d0bb', '#5a3a28', '#3a2a20', '#6b4a34', False),
    'palace': ('#efe8d6', '#d9d0bb', '#a03a2c', '#2f5a4a', '#4f8a72', False),
    'wall': ('#d9c6a4', '#bfa987', '#8f8a80', '#6f6a62', '#a8a398', False),
}
OFFICE = ('office_beige', 'office_grey', 'civic', 'glass_blue', 'glass_teal', 'resi')
AWN = ['#c8473c', '#2f6fb3', '#e0a52e', '#3d8f5a', '#6b5a4a', '#d8d2c4']

def facade_tex(kind):
    wall, dark, frame, glass, glass2, brick = FAC[kind]
    n = 5; tw, th = int(BAY * PPM), int(FLH * PPM)
    im = Image.new('RGB', (tw * n, th * 2), wall); d = ImageDraw.Draw(im)
    rnd = random.Random(__import__('zlib').crc32(kind.encode()))
    for row in range(2):
        for col in range(n):
            ox, oy = col * tw, row * th  # row 0 = 위층, row 1 = 1층 상가 (이미지 위쪽이 v=1)
            if brick:
                for y in range(0, th, 4):
                    d.line([(ox, oy + y), (ox + tw - 1, oy + y)], fill=dark)
                    for x in range((y // 4 % 2) * 6, tw, 12): d.line([(ox + x, oy + y), (ox + x, oy + y + 3)], fill=dark)
            else:
                d.line([(ox, oy + th - 2), (ox + tw - 1, oy + th - 2)], fill=dark)  # 층 띠
                for _ in range(10):
                    x, y = rnd.randrange(tw), rnd.randrange(th); d.line([(ox + x, oy + y), (ox + x + rnd.randrange(3, 9), oy + y)], fill=dark)
            if col == 4: continue  # 빈 벽
            if kind == 'wall':  # 사괴석 담: 아래 큰 돌, 위 작은 돌 줄
                d.rectangle([ox, oy, ox + tw, oy + th], fill=wall)
                for y in range(0, th - 34, 9):
                    d.line([(ox, oy + y), (ox + tw, oy + y)], fill=dark)
                    for x in range((y // 9 % 2) * 7, tw, 14): d.line([(ox + x, oy + y), (ox + x, oy + y + 8)], fill=dark)
                d.rectangle([ox, oy + th - 34, ox + tw, oy + th], fill=glass2)
                for y in (th - 34, th - 17): d.line([(ox, oy + y), (ox + tw, oy + y)], fill=glass)
                for x in range(0, tw, 26):
                    d.line([(ox + x, oy + th - 34), (ox + x, oy + th - 17)], fill=glass); d.line([(ox + x + 13, oy + th - 17), (ox + x + 13, oy + th)], fill=glass)
                continue
            if kind == 'palace':
                d.rectangle([ox, oy, ox + tw, oy + 12], fill='#2f6f5a')  # 단청 띠
                for x in range(0, tw, 8): d.rectangle([ox + x, oy + 3, ox + x + 3, oy + 8], fill='#c9483a' if (x // 8) % 2 else '#e8c95a')
                d.rectangle([ox, oy + 12, ox + tw, oy + 16], fill=frame)
                for x in (0, tw // 2 - 3, tw - 6): d.rectangle([ox + x, oy + 12, ox + x + 6, oy + th], fill=frame)  # 붉은 기둥
                for x in (9, tw // 2 + 6):
                    d.rectangle([ox + x, oy + 20, ox + x + 36, oy + th - 6], fill=frame)
                    d.rectangle([ox + x + 2, oy + 22, ox + x + 34, oy + th - 30], fill=glass2)
                    for xx in range(x + 6, x + 34, 5): d.line([(ox + xx, oy + 22), (ox + xx, oy + th - 30)], fill=glass)
                    for yy in range(oy + 28, oy + th - 30, 7): d.line([(ox + x + 2, yy), (ox + x + 34, yy)], fill=glass)
                continue
            if kind == 'hanok':
                d.rectangle([ox, oy + th - 20, ox + tw, oy + th], fill='#9a958a')  # 화강석 기단
                for x in range(0, tw, 16): d.line([(ox + x, oy + th - 20), (ox + x, oy + th)], fill='#7d786e')
                for x in (0, tw // 2, tw - 4): d.rectangle([ox + x, oy, ox + x + 3, oy + th - 20], fill=frame)  # 기둥
                d.rectangle([ox, oy + 6, ox + tw, oy + 9], fill=frame); d.rectangle([ox, oy + th - 40, ox + tw, oy + th - 37], fill=frame)
                for k, x in enumerate((10, tw // 2 + 8)):
                    if (col + k) % 3 == 0: continue
                    d.rectangle([ox + x, oy + 18, ox + x + 34, oy + th - 42], fill='#e9dfc6', outline=frame)  # 창호지 문
                    for xx in range(x + 6, x + 34, 6): d.line([(ox + xx, oy + 18), (ox + xx, oy + th - 42)], fill=glass2)
                    for yy in range(oy + 26, oy + th - 42, 8): d.line([(ox + x, yy), (ox + x + 34, yy)], fill=glass2)
                continue
            if row == 0 and kind in OFFICE:
                d.rectangle([ox, oy + 20, ox + tw, oy + th - 28], fill=glass)
                d.polygon([(ox, oy + th - 28), (ox, oy + 44), (ox + 40, oy + 20), (ox + 70, oy + 20)], fill=glass2)
                for x in (0, tw // 3, 2 * tw // 3, tw - 3): d.rectangle([ox + x, oy + 14, ox + x + 2, oy + th - 22], fill=frame)
                d.rectangle([ox, oy + 16, ox + tw, oy + 19], fill=frame); d.rectangle([ox, oy + th - 28, ox + tw, oy + th - 25], fill=frame)
                if col == 2: d.rectangle([ox + tw // 3 + 3, oy + 20, ox + 2 * tw // 3, oy + th - 28], fill=glass2)
                continue
            if row == 0:
                wx, wy, ww_, wh_ = (tw - 52) // 2, 26, 52, 46
                if col == 1: wx, ww_ = (tw - 70) // 2, 70
                if col == 3: wy, wh_ = 18, 62
                d.rectangle([ox + wx - 3, oy + wy - 3, ox + wx + ww_ + 3, oy + wy + wh_ + 3], fill=frame)
                d.rectangle([ox + wx, oy + wy, ox + wx + ww_, oy + wy + wh_], fill=glass)
                d.polygon([(ox + wx, oy + wy + wh_), (ox + wx, oy + wy + wh_ // 2), (ox + wx + ww_ // 2, oy + wy)], fill=glass2)
                d.line([(ox + wx + ww_ // 2, oy + wy), (ox + wx + ww_ // 2, oy + wy + wh_)], fill=frame, width=2)
                d.rectangle([ox + wx - 5, oy + wy + wh_ + 3, ox + wx + ww_ + 5, oy + wy + wh_ + 6], fill=dark)  # 창대
                if col == 2: d.rectangle([ox + wx + 6, oy + wy + wh_ + 8, ox + wx + 30, oy + wy + wh_ + 20], fill='#e4e4de', outline='#8e8e88')  # 실외기
            else:
                sc = AWN[(col * 2 + __import__('zlib').crc32(kind.encode())) % len(AWN)]
                d.rectangle([ox + 3, oy + 6, ox + tw - 4, oy + 24], fill=sc)  # 간판 띠(글자 없음)
                d.rectangle([ox + 8, oy + 12, ox + tw - 9, oy + 18], fill='#f3efe4')
                d.rectangle([ox + 5, oy + 30, ox + tw - 6, oy + th - 6], fill=frame)
                d.rectangle([ox + 8, oy + 33, ox + tw - 40, oy + th - 12], fill=glass)
                d.polygon([(ox + 8, oy + th - 12), (ox + 8, oy + 50), (ox + 40, oy + 33)], fill=glass2)
                d.rectangle([ox + tw - 36, oy + 33, ox + tw - 9, oy + th - 6], fill='#4a3a30')  # 문
                d.rectangle([ox + tw - 32, oy + 38, ox + tw - 13, oy + 62], fill=glass2)
    p = f'{TEXD}/tex_{kind}.png'; im.save(p); return p

_mat = {}
def mat_flat(hexs):
    if hexs in _mat: return _mat[hexs]
    m = bpy.data.materials.new(hexs); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = lin(hexs)
    b.inputs['Roughness'].default_value = 1.0; b.inputs['Specular IOR Level'].default_value = 0.0
    _mat[hexs] = m; return m

def mat_tex(path, key):
    if key in _mat: return _mat[key]
    m = bpy.data.materials.new(key); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes['Principled BSDF']; b.inputs['Roughness'].default_value = 1.0; b.inputs['Specular IOR Level'].default_value = 0.0
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path); t.interpolation = 'Linear'; t.extension = 'REPEAT'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color']); _mat[key] = m; return m

def mat_vcol():
    if 'vcol' in _mat: return _mat['vcol']
    m = bpy.data.materials.new('vcol'); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes['Principled BSDF']; b.inputs['Roughness'].default_value = 1.0; b.inputs['Specular IOR Level'].default_value = 0.0
    a = nt.nodes.new('ShaderNodeAttribute'); a.attribute_name = 'col'
    nt.links.new(a.outputs['Color'], b.inputs['Base Color']); _mat['vcol'] = m; return m

CREATED = []  # 만든 오브젝트 순서대로(전각 자리 표시용)
class MB:  # 메시 조립기
    def __init__(s): s.v = []; s.f = []; s.fm = []; s.uv = []; s.mats = []
    def mi(s, m):
        if m not in s.mats: s.mats.append(m)
        return s.mats.index(m)
    def face(s, pts, m, uv=None):
        i = len(s.v); s.v += [tuple(p) for p in pts]; s.f.append(list(range(i, i + len(pts)))); s.fm.append(s.mi(m))
        s.uv.append(uv or [(0, 0)] * len(pts))
    def box(s, c, sx, sy, sz, m, ang=0.0, top=None):
        ca, sa = math.cos(ang), math.sin(ang)
        q = [(c[0] + ca * dx - sa * dy, c[1] + sa * dx + ca * dy) for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy))]
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]; s.face([(a[0], a[1], c[2]), (b[0], b[1], c[2]), (b[0], b[1], c[2] + sz), (a[0], a[1], c[2] + sz)], m)
        s.face([(x, y, c[2] + sz) for x, y in q], top or m)
    def cyl(s, c, r, h, m, top=None, n=12):
        ring = [(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]; s.face([(a[0], a[1], c[2]), (b[0], b[1], c[2]), (b[0], b[1], c[2] + h), (a[0], a[1], c[2] + h)], m)
        s.face([(x, y, c[2] + h) for x, y in ring], top or m)
    def build(s, name, idx, smooth=False):
        me = bpy.data.meshes.new(name); me.from_pydata(s.v, [], s.f)
        for m in s.mats: me.materials.append(m)
        me.polygons.foreach_set('material_index', s.fm)
        uvl = me.uv_layers.new(name='uv'); flat = [c for f in s.uv for u in f for c in u]; uvl.data.foreach_set('uv', flat)
        me.update(); o = bpy.data.objects.new(name, me); o.pass_index = idx; bpy.context.scene.collection.objects.link(o); CREATED.append(o); return o

def walls(mb, poly, z0, z1, kind, store, seed, flh, bay=None):
    bay = bay or BAY
    tex = mat_tex(facade_tex(kind), 'tex_' + kind); rnd = random.Random(seed)
    nfl = max(1, round((z1 - z0) / flh)); fh = (z1 - z0) / nfl
    for ring in [poly.exterior] + list(poly.interiors):
        c = list(ring.coords)
        for a, b in zip(c[:-1], c[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 0.05: continue
            nb = max(1, round(L / bay)) if L >= 2.2 else 1
            for k in range(nb):
                p = (a[0] + (b[0] - a[0]) * k / nb, a[1] + (b[1] - a[1]) * k / nb); q = (a[0] + (b[0] - a[0]) * (k + 1) / nb, a[1] + (b[1] - a[1]) * (k + 1) / nb)
                for f in range(nfl):
                    col = 4 if L < 2.2 else rnd.choice([0, 0, 0, 1, 2, 3] if not (store and f == 0) else [0, 1, 2, 3])
                    if kind not in ('hanok', 'palace', 'wall') and kind not in OFFICE and L >= 2.2 and rnd.random() < 0.12: col = 4
                    row = 1 if (store and f == 0 and kind != 'hanok') else 0
                    u0, u1 = col / 5, (col + 1) / 5; v1 = 1 - row / 2; v0 = v1 - 0.5
                    za, zb = z0 + f * fh, z0 + (f + 1) * fh
                    mb.face([(p[0], p[1], za), (q[0], q[1], za), (q[0], q[1], zb), (p[0], p[1], zb)], tex, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
                    if row == 1 and col != 4 and rnd.random() < 0.6:  # 차양
                        nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L; am = mat_flat(rnd.choice(AWN[:5]))
                        mb.face([(p[0], p[1], za + 2.75), (q[0], q[1], za + 2.75), (q[0] + nx * .8, q[1] + ny * .8, za + 2.3), (p[0] + nx * .8, p[1] + ny * .8, za + 2.3)], am)

ROOF = {'roof_green': '#5f9a55', 'roof_concrete': '#a5a39c', 'roof_dark': '#4a4d55', 'roof_tile': '#b4664a'}
def modern(b, idx):
    poly = orient(Polygon(b['rings'][0], b['rings'][1:]).buffer(0), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 4: return
    h = max(3.0, b['h']); rnd = random.Random(b['seed']); mb = MB()
    fac = {'office_stone': 'office_beige', 'civic_stone': 'civic', 'curtain_glass': 'glass_blue', 'resi_tower': 'resi'}.get(b['fac'])
    if fac is None: fac = rnd.choice(['brick_red', 'brick_brown', 'brick_beige']) if b['fac'] == 'brick' else rnd.choice(['stucco_white', 'stucco_cream', 'stucco_grey', 'stucco_sand'])
    if fac == 'office_beige' and rnd.random() < .4: fac = 'office_grey'
    if h > 22 and fac not in OFFICE: fac = rnd.choice(['office_beige', 'office_grey', 'glass_blue', 'glass_teal'])
    walls(mb, poly, 0, h, fac, b.get('storefront'), b['seed'], b.get('flh') or 3.2, bay=4.2 if fac in OFFICE else None)
    rc = ROOF.get(b.get('roofcol'), '#a5a39c'); roofm = mat_flat(rc); capm = mat_flat(FAC[fac][1]); wallm = mat_flat(FAC[fac][0])
    inner = poly.buffer(-0.28, join_style=2)
    if b.get('parapet') and inner.geom_type == 'Polygon' and inner.area > 6 and not inner.interiors and not poly.interiors:
        zt = h + 0.55
        for ring, flip in ((poly.exterior, False), (inner.exterior, True)):
            c = list(ring.coords)
            for a, q in zip(c[:-1], c[1:]):
                pts = [(a[0], a[1], h), (q[0], q[1], h), (q[0], q[1], zt), (a[0], a[1], zt)]
                mb.face(pts[::-1] if flip else pts, wallm)
        for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms:
            mb.face([(x, y, zt) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], capm)
        mb.face([(x, y, h) for x, y in list(orient(inner, 1.0).exterior.coords)[:-1]], roofm); zr = h
    else:
        for t in shapely.constrained_delaunay_triangles(poly).geoms: mb.face([(x, y, h) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], roofm)
        zr = h; inner = poly
    # 옥상 설비
    area = inner.buffer(-1.3)
    def spot():
        if area.is_empty: return None
        x0, y0, x1, y1 = area.bounds
        for _ in range(30):
            p = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
            if area.contains(p): return p.x, p.y
    ang = math.atan2(*(np.subtract(poly.exterior.coords[1], poly.exterior.coords[0])[::-1]))
    if b.get('penthouse') and (s := spot()):
        mb.box((s[0], s[1], zr), 1.6, 1.4, 2.5, wallm, ang, mat_flat('#8d8b84'))
    if rnd.random() < 0.55 and (s := spot()):
        tc = rnd.choice(['#e8b62c', '#e8b62c', '#3f86c9', '#d9d9d2'])
        for dx, dy in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)): mb.box((s[0] + dx, s[1] + dy, zr), .06, .06, .7, mat_flat('#5a5a58'))
        mb.cyl((s[0], s[1], zr + .7), .75, 1.3, mat_flat(tc), mat_flat('#f2efe4' if tc != '#d9d9d2' else '#b9b9b2'))
    for _ in range(rnd.randrange(0, 3)):
        if (s := spot()): mb.box((s[0], s[1], zr), .5, .25, .7, mat_flat('#e2e2dc'), ang + rnd.choice([0, math.pi / 2]), mat_flat('#bdbdb6'))
    if rnd.random() < 0.3 and (s := spot()):
        mb.box((s[0], s[1], zr), .9, .6, .12, mat_flat('#8a6a4a'), ang)  # 평상
    mb.build('b%d' % idx, idx)

# ================= v2: 지붕(우진각·맞배·팔작·중층·처마 곡선), 궁궐, 문루, 담, 나무, 지면, 패스 =================
import zlib
from shapely.geometry import LineString
from shapely.ops import unary_union, polygonize, substring
from shapely.strtree import STRtree
STY = {  # 벽 텍스처, 처마 내밀기, 물매, 마루 색, 처마 밑 색, 모서리 들림
    'hanok': ('hanok', 0.75, 0.58, '#6f7278', '#6a4630', 0.22),
    'palace': ('palace', 1.5, 0.62, '#b9b7ae', '#2f6f5a', 0.5),
    'wall': ('wall', 0.28, 0.9, '#5d6066', '#3a3c42', 0.0),
}
TILE = [np.array(lin(c)) for c in ('#3b3e46', '#5a5e68', '#24262b', '#8f9298')]  # 바탕, 수키와 등, 골, 막새

def roof(eave, base, z_e, sty, seed, idx, form='hip', tier=None):
    """높이장 지붕. eave=처마 다각형, base=몸체 다각형. form: hip|gable|paljak. tier=(dr, wallh): 중층."""
    kind, over, slope, rdgc, woodc, lift = STY[sty]
    G = 0.05 if eave.area < 700 else 0.08
    x0, y0, x1, y1 = eave.bounds
    xs = np.arange(x0 - G, x1 + 2 * G, G); ys = np.arange(y0 - G, y1 + 2 * G, G); gx, gy = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(eave, gx, gy)
    mrr = base.minimum_rotated_rectangle; mc = np.array(mrr.exterior.coords)
    e0, e1 = mc[1] - mc[0], mc[2] - mc[1]; ax = e0 if np.hypot(*e0) >= np.hypot(*e1) else e1; ax = ax / max(np.hypot(*ax), 1e-9)
    halfw = min(np.hypot(*e0), np.hypot(*e1)) / 2
    BIG = 1e9
    d1 = np.full(gx.shape, BIG); tt = np.zeros(gx.shape); eid = np.zeros(gx.shape, np.int32)
    dL = np.full(gx.shape, BIG); tL = np.zeros(gx.shape); eL = np.zeros(gx.shape, np.int32)
    dS = np.full(gx.shape, BIG); tS = np.zeros(gx.shape); eS = np.zeros(gx.shape, np.int32)
    dc = np.full(gx.shape, BIG); off = 0.0; ek = 0
    for ring in [eave.exterior] + list(eave.interiors):
        c = np.array(ring.coords)[:-1]; n = len(c); rec = []
        for k in range(n):
            a, q = c[k], c[(k + 1) % n]; e = q - a; L = np.hypot(*e)
            tr = ((gx - a[0]) * e[0] + (gy - a[1]) * e[1]) / max(L * L, 1e-12); t = np.clip(tr, 0, 1)
            d = np.hypot(gx - (a[0] + t * e[0]), gy - (a[1] + t * e[1]))
            dl = np.abs((gx - a[0]) * e[1] - (gy - a[1]) * e[0]) / max(L, 1e-6)
            rec.append((d, dl, tr, L, off, ek, abs(e @ ax) / max(L, 1e-9) > 0.7)); off += math.ceil(L / .34) * .34; ek += 1
            p, nx = c[k - 1], c[(k + 1) % n]  # 볼록 꼭짓점까지 거리(처마 들림)
            if (a[0] - p[0]) * (nx[1] - a[1]) - (a[1] - p[1]) * (nx[0] - a[0]) > 0: dc = np.minimum(dc, np.hypot(gx - a[0], gy - a[1]))
        for k in range(n):
            d, dl, tr, L, o, ei, isL = rec[k]; pd, pdl, ptr, pL, po, pei, _ = rec[k - 1]
            ve = (tr <= 0) & (ptr >= 1)  # 오목 모서리 부채꼴 → 골(valley)
            dv = np.where(ve, np.maximum(dl, pdl), d); tv = np.where(ve & (pdl > dl), po + ptr * pL, o + tr * L); ev = np.where(ve & (pdl > dl), pei, ei)
            new = dv < d1; tt = np.where(new, tv, tt); eid = np.where(new, ev, eid); d1 = np.where(new, dv, d1)
            if isL: new = dl < dL; tL = np.where(new, o + tr * L, tL); eL = np.where(new, ei, eL); dL = np.where(new, dl, dL)
            else: new = d < dS; tS = np.where(new, o + tr * L, tS); eS = np.where(new, ei, eS); dS = np.where(new, d, dS)
    kk = over + min(1.9, 0.38 * halfw)  # 팔작 합각 시작 깊이
    if form != 'hip' and (np.any(dL[inside] > 1e8) or np.any(dS[inside] > 1e8)): form = 'hip'  # 변 분류 실패 → 우진각
    def F(a1, aL, aS):  # 형태별 높이, 기와골 좌표, 변 번호, 합각벽 띠
        if form == 'gable': return slope * aL, tL, eL, np.zeros(gx.shape, bool)
        if form == 'paljak':
            sk = (aS < kk); useS = sk & (aS < aL)
            return np.where(sk, slope * np.minimum(aL, aS), slope * aL), np.where(useS, tS, tL), np.where(useS, eS, eL), (aS >= kk - G) & (aS < kk + 2 * G) & (aL > kk + 0.15)
        return slope * a1, tt, eid, np.zeros(gx.shape, bool)
    if tier:
        dr, wallh = tier; inner = d1 >= dr
        zi, ti, ei2, gw = F(d1 - dr, dL - dr, dS - dr)
        zf = np.where(inner, slope * dr + wallh + zi, slope * d1); tu = np.where(inner, ti, tt); eu = np.where(inner, ei2 + 1000, eid)
        tw = (d1 >= dr - G) & (d1 < dr + 2 * G); gw = gw & inner; dloc = np.where(inner, zi, slope * d1) / slope
    else:
        zf, tu, eu, gw = F(d1, dL, dS); tw = np.zeros(gx.shape, bool); dloc = zf / slope
    rib = np.maximum(0, np.cos(2 * np.pi * tu / 0.34)); step = (dloc % 0.42) / 0.42
    # 마루: 변 번호가 바뀌는 곳 중 볼록한 곳만(골은 제외)
    ch = np.zeros(gx.shape, bool)
    for sh, axn in ((1, 0), (-1, 0), (1, 1), (-1, 1)): ch |= eu != np.roll(eu, sh, axn)
    for _ in range(1): ch = ch | np.roll(ch, 1, 0) | np.roll(ch, -1, 0) | np.roll(ch, 1, 1) | np.roll(ch, -1, 1)
    r = 6; lap = zf - (np.roll(zf, r, 0) + np.roll(zf, -r, 0) + np.roll(zf, r, 1) + np.roll(zf, -r, 1)) / 4
    jz = tw | gw
    for _ in range(4): jz = jz | np.roll(jz, 1, 0) | np.roll(jz, -1, 0) | np.roll(jz, 1, 1) | np.roll(jz, -1, 1)
    ridge = ch & (lap > 0.03) & ~jz
    up = lift * np.clip(1 - dc / 2.4, 0, 1) ** 2 * np.clip(1 - d1 / 1.3, 0, 1) if lift else 0
    z = z_e + 0.06 + zf + 0.055 * rib ** 0.6 + 0.025 * step + np.where(ridge, 0.15, 0) + up
    colv = np.zeros(gx.shape + (4,)); colv[:] = TILE[0]; colv[rib > 0.8] = TILE[1]; colv[rib < 0.12] = TILE[2]; colv[(step > 0.88) & (rib < 0.8)] = TILE[2]
    colv[ridge] = np.array(lin(rdgc)); colv[d1 < 0.14] = TILE[3]
    colv[gw] = np.array(lin('#e6dcc6' if sty != 'palace' else '#a8442f')); colv[tw] = np.array(lin('#a03a2c' if sty == 'palace' else '#efe8d6')); colv[tw & (d1 >= (tier[0] if tier else 0))] = np.array(lin('#2b4a3f' if sty == 'palace' else '#6a4630'))
    if SAVE_BLEND:  # 공개 .blend: 메시 대신 높이·색 그림 + 지오메트리 노드(같은 정점·면을 Blender 가 다시 만든다, common/roofgrid.py)
        o = roofgrid.build('roof%d' % idx, idx, xs, ys, z, colv, inside, mat_vcol(), TEXD, bpy.context.scene.collection.objects.link); CREATED.append(o)
        return slope, ax
    idxm = -np.ones(gx.shape, int); idxm[inside] = np.arange(inside.sum())
    V = np.stack([gx[inside], gy[inside], z[inside]], 1)
    a_, b_, c_, d_ = idxm[:-1, :-1], idxm[:-1, 1:], idxm[1:, 1:], idxm[1:, :-1]; ok = (a_ >= 0) & (b_ >= 0) & (c_ >= 0) & (d_ >= 0)
    me = bpy.data.meshes.new('roof%d' % idx); me.from_pydata(V.tolist(), [], np.stack([a_[ok], b_[ok], c_[ok], d_[ok]], 1).tolist()); me.materials.append(mat_vcol())
    ca = me.color_attributes.new('col', 'FLOAT_COLOR', 'POINT'); ca.data.foreach_set('color', colv[inside].ravel())
    me.update(); o = bpy.data.objects.new('roof%d' % idx, me); o.pass_index = idx; bpy.context.scene.collection.objects.link(o); CREATED.append(o)
    return slope, ax

def roofed(poly, idx, seed, sty='hanok', eave_h=3.0, z0=0.0, form=None, tier=False, platform=None):
    poly = orient(poly.buffer(0), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 1.5: return
    kind, over, slope, rdgc, woodc, lift = STY[sty]; mb = MB(); rnd = random.Random(seed)
    mrr = poly.minimum_rotated_rectangle; mc = np.array(mrr.exterior.coords); s0, s1 = np.hypot(*(mc[1] - mc[0])), np.hypot(*(mc[2] - mc[1]))
    rect = (not poly.interiors) and poly.area / max(mrr.area, 1e-6) > 0.86 and max(s0, s1) / max(min(s0, s1), 1e-6) > 1.25
    if form is None: form = 'hip' if sty == 'wall' or not rect else rnd.choices(['paljak', 'gable', 'hip'], [0.55, 0.3, 0.15] if sty == 'hanok' else [0.8, 0.0, 0.2])[0]
    if not rect and form != 'hip': form = 'hip'
    if poly.area > 250 and sty == 'palace': over = 2.1
    for platform in (platform if isinstance(platform, list) else [platform] if platform else []):  # 월대(여러 단 가능, 바깥 단부터)
        pw, ph = platform; pp = orient(poly.buffer(pw, join_style=2), 1.0); stone = mat_flat('#c9c6bc'); sd = mat_tex(facade_tex('wall'), 'tex_wall')
        c = list(pp.exterior.coords); per = 0
        for a_, q in zip(c[:-1], c[1:]):
            L = math.hypot(q[0] - a_[0], q[1] - a_[1]); u0, u1 = per / BAY / 5 % 1 * 0, L / BAY / 5
            mb.face([(a_[0], a_[1], z0), (q[0], q[1], z0), (q[0], q[1], z0 + ph), (a_[0], a_[1], z0 + ph)], sd, [(0, .5), (min(u1, .2), .5), (min(u1, .2), .5 + .5 * min(1, ph / FLH)), (0, .5 + .5 * min(1, ph / FLH))])
        mb.face([(x, y, z0 + ph) for x, y in c[:-1]], stone); z0 += ph
    ze = z0 + eave_h
    walls(mb, poly, z0, ze, kind, False, seed, max(3.2, eave_h) if sty != 'hanok' else 3.2)
    eave = orient(poly.buffer(over, join_style=2, mitre_limit=5.0).simplify(0.03), 1.0)
    if eave.geom_type != 'Polygon': return
    wood = mat_flat(woodc)
    for ring in [eave.exterior] + list(eave.interiors):  # 처마 밑 판(직선 실루엣)
        c = list(ring.coords)
        for a_, q in zip(c[:-1], c[1:]): mb.face([(a_[0], a_[1], ze - .18), (q[0], q[1], ze - .18), (q[0], q[1], ze + .06), (a_[0], a_[1], ze + .06)], wood)
    halfw = min(s0, s1) / 2
    tr = (min(2.6, 0.42 * halfw) + over, 1.9 if poly.area < 500 else 2.6) if tier else None
    sl, ax = roof(eave, poly, ze, sty, seed, idx, form, tr)
    if form == 'gable':  # 박공벽
        gm = mat_flat('#e6dcc6'); c = list(poly.exterior.coords); Ls = [(np.array(a_), np.array(q)) for a_, q in zip(c[:-1], c[1:]) if abs((np.array(q) - np.array(a_)) @ ax) / max(np.hypot(*(np.array(q) - np.array(a_))), 1e-9) > 0.7]
        def dline(p): return min(abs((p[0] - a_[0]) * (q[1] - a_[1]) - (p[1] - a_[1]) * (q[0] - a_[0])) / max(np.hypot(*(q - a_)), 1e-9) for a_, q in Ls) if Ls else 0
        for a_, q in zip(c[:-1], c[1:]):
            a_, q = np.array(a_), np.array(q); L = np.hypot(*(q - a_))
            if L < 0.3 or abs((q - a_) @ ax) / L > 0.7: continue
            m = max(2, int(L / 0.25)); pts = [a_ + (q - a_) * i / m for i in range(m + 1)]
            for p, r_ in zip(pts[:-1], pts[1:]):
                mb.face([(p[0], p[1], ze), (r_[0], r_[1], ze), (r_[0], r_[1], ze + sl * (dline(r_) + over) + .04), (p[0], p[1], ze + sl * (dline(p) + over) + .04)], gm)
    mb.build('h%d' % idx, idx)

def gate(poly, idx, seed, base_h, tier):
    """석축 문루: 화강석 육축(홍예 3개) 위에 목조 문루."""
    poly = orient(poly.buffer(0), 1.0); mrr = orient(poly.minimum_rotated_rectangle, 1.0); c = list(mrr.exterior.coords)[:-1]
    tw, th = 512, 128; im = Image.new('RGB', (tw, th), '#b9b6ac'); d = ImageDraw.Draw(im)
    for y in range(0, th, 12):
        d.line([(0, y), (tw, y)], fill='#96938a')
        for x in range((y // 12 % 2) * 16, tw, 32): d.line([(x, y), (x, y + 11)], fill='#96938a')
    for cxp, w_ in ((tw // 2, 54), (tw // 2 - 120, 42), (tw // 2 + 120, 42)):
        d.pieslice([cxp - w_ // 2 - 4, th - 96, cxp + w_ // 2 + 4, th - 96 + w_ + 8], 180, 360, fill='#8a877e'); d.rectangle([cxp - w_ // 2 - 4, th - 96 + w_ // 2 + 4, cxp + w_ // 2 + 4, th], fill='#8a877e')
        d.pieslice([cxp - w_ // 2, th - 92, cxp + w_ // 2, th - 92 + w_], 180, 360, fill='#2a2622'); d.rectangle([cxp - w_ // 2, th - 92 + w_ // 2, cxp + w_ // 2, th], fill='#2a2622')
    p = f'{TEXD}/tex_gate.png'; im.save(p); gm = mat_tex(p, 'tex_gate'); mb = MB(); plain = mat_flat('#b9b6ac')
    Ls = [math.hypot(c[(k + 1) % 4][0] - c[k][0], c[(k + 1) % 4][1] - c[k][1]) for k in range(4)]
    for k in range(4):
        a_, q = c[k], c[(k + 1) % 4]; pts = [(a_[0], a_[1], 0), (q[0], q[1], 0), (q[0], q[1], base_h), (a_[0], a_[1], base_h)]
        mb.face(pts, gm if Ls[k] >= max(Ls) - 0.5 else plain, [(0, 0), (1, 0), (1, 1), (0, 1)])
    mb.face([(x, y, base_h) for x, y in c], mat_flat('#c9c6bc'))
    par = mrr.buffer(-0.5, join_style=2)  # 여장
    if par.geom_type == 'Polygon':
        for t in shapely.constrained_delaunay_triangles(mrr.difference(par)).geoms: mb.face([(x, y, base_h + .9) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], plain)
        for ring, fl in ((mrr.exterior, False), (par.exterior, True)):
            cc = list(ring.coords)
            for a_, q in zip(cc[:-1], cc[1:]):
                pts = [(a_[0], a_[1], base_h), (q[0], q[1], base_h), (q[0], q[1], base_h + .9), (a_[0], a_[1], base_h + .9)]; mb.face(pts[::-1] if fl else pts, plain)
    mb.build('g%d' % idx, idx)
    top = mrr.buffer(-2.2, join_style=2)
    if top.geom_type == 'Polygon' and top.area > 8: roofed(top, idx, seed, 'palace', 3.4, base_h, 'hip', tier)

def blob(mb, c, r, m, sq=1.0, n=7):
    rings = [(0, -1)] + [(math.cos(a), math.sin(a)) for a in (-0.6, 0.15, 0.85)] + [(0, 1)]
    prev = None
    for cr, sr in rings:
        ring = [(c[0] + r * cr * math.cos(2 * math.pi * k / n), c[1] + r * cr * math.sin(2 * math.pi * k / n), c[2] + r * sq * sr) for k in range(n)]
        if prev:
            for k in range(n): mb.face([prev[k], prev[(k + 1) % n], ring[(k + 1) % n], ring[k]], m)
        prev = ring

GREENS = ['#4f8f3f', '#5a9a45', '#3f7d3a', '#6aa84e', '#467f48']
def tree(i, x, y, r):
    rnd = random.Random(900 + i); mb = MB(); pine = rnd.random() < 0.28; th = 1.8 + r * 0.5
    mb.cyl((x, y, 0), 0.16 + r * 0.04, th + (r if pine else 0.3), mat_flat('#6b4b34'), n=6)
    if pine:
        g = mat_flat(rnd.choice(['#2f6b3d', '#356f43', '#2a6038']))
        for k in range(3): mb.cyl((x + rnd.uniform(-.3, .3), y + rnd.uniform(-.3, .3), th + k * r * .45), r * (1.0 - k * .27), r * .35, g, mat_flat('#3f7d4a'), n=8)
    else:
        g = [mat_flat(c) for c in rnd.sample(GREENS, 2)]
        blob(mb, (x, y, th + r * .75), r, g[0], 0.85)
        for k in range(rnd.randrange(1, 4)):
            a = rnd.uniform(0, 6.28); blob(mb, (x + math.cos(a) * r * .55, y + math.sin(a) * r * .55, th + r * rnd.uniform(.5, 1.1)), r * rnd.uniform(.5, .7), g[k % 2], 0.85)
    mb.build('t%d' % i, 22000 + i)

def unproj(px, py, z=0.0):
    u = (px - W / 2) * PX + CX - EX[2] * z; v = CY - (py - H / 2) * PX - EY[2] * z
    x, y = np.linalg.solve(np.array([[EX[0], EX[1]], [EY[0], EY[1]]]), [u, v]); return (float(x), float(y), z)
def inwin(c, h=3.0, extra=0):
    px, py = proj([c[0], c[1], h / 2]); mg = 500 + h * 30 + extra
    return X0 - mg < px < X0 + WW + mg and Y0 - mg < py < Y0 + WH + mg

# ---------- KHS 개별 전각(국가유산청 3D 기록, 모델당 변환 캐시 .blend) ----------
# P3D_KHSP=<placements_v2.json> 이 주어지고 파일이 있을 때만 켜진다(없으면 기존 동작 그대로). 만드는 곳: 국가유산청 모델 정합 도구(이 저장소에 없음)
# 배치: 지도 xy = R(theta)·모델 xy + (tx,ty). footprint(처마 포함 평면)로 덮이는 절차 건물·담 조각·나무를 뺀다.
KHSP = os.environ.get('P3D_KHSP', '')
KPL = json.load(open(KHSP))['models'] if KHSP and os.path.exists(KHSP) else {}
KFP = {n_: unary_union([Polygon(c_).buffer(0) for c_ in v_['footprint']]) for n_, v_ in KPL.items()}
from mathutils import Euler
KSUN = (Euler((math.radians(50), 0, math.radians(-28))).to_matrix() @ Vector((0, 0, -1))) if KPL else None  # 아래 태양(so)과 같은 회전
def khs_inwin(fp, zmax, mg=64):
    """KHS 모델이 창에 보이거나 그림자를 드리우는지: 평면 꼭짓점의 바닥·지붕 높이 투영과 그림자 끝점의 화면 bbox가 창(+mg px)과 겹치는가."""
    sx_, sy_ = KSUN.x / -KSUN.z * zmax, KSUN.y / -KSUN.z * zmax; us_, vs_ = [], []
    for g_ in (fp.geoms if hasattr(fp, 'geoms') else [fp]):
        for x_, y_ in g_.exterior.coords:
            for p_ in ((x_, y_, 0.0), (x_, y_, zmax), (x_ + sx_, y_ + sy_, 0.0)):
                u_, w_ = proj(p_); us_.append(u_); vs_.append(w_)
    return min(us_) < X0 + WW + mg and max(us_) > X0 - mg and min(vs_) < Y0 + WH + mg and max(vs_) > Y0 - mg
# 이 창에서 실제로 불러올 모델만 남긴다. 제외(절차 건물·담·나무)도 불러온 모델 평면으로만 한다 — 안 불러온 모델 자리의 화면 밖 절차 건물은 그대로 그림자를 드리운다.
KPL = {n_: v_ for n_, v_ in KPL.items() if khs_inwin(KFP[n_], v_['zmax'])}
KFP = {n_: KFP[n_] for n_ in KPL}
KFP_B = unary_union([g_ for n_, g_ in KFP.items() if not KPL[n_].get('keep_trees')]) if KPL else None
KSKIPK = {k_ for v_ in KPL.values() for k_ in v_.get('osm_k', [])}
KFP_ALL = unary_union(list(KFP.values())) if KPL else None
def khs_cov(p):  # p 면적 중 KHS 평면(처마 포함)에 덮인 비율
    if not KPL or p.is_empty or p.area <= 0 or not KFP_ALL.intersects(p): return 0.0
    return KFP_ALL.intersection(p).area / p.area
def khs_place():
    nk = 0; img0_ = set(bpy.data.images); names_ = []
    for n_, v_ in sorted(KPL.items(), key=lambda kv: kv[1]['pass_index']):
        with bpy.data.libraries.load(v_['blend'], link=False) as (src_, dst_): dst_.objects = [o_ for o_ in src_.objects if o_ in ('KHSB', 'KHSG')]
        rt_ = bpy.data.objects.new('KHSR_%d' % v_['pass_index'], None); sc.collection.objects.link(rt_)
        for o_ in dst_.objects:
            if o_ is None: continue
            sc.collection.objects.link(o_); o_.parent = rt_; o_.pass_index = 1 if o_.name.startswith('KHSG') else v_['pass_index']
        rt_.rotation_euler = (0, 0, math.radians(v_['theta'])); rt_.location = (v_['tx'], v_['ty'], v_.get('tz', 0.0))
        META[v_['pass_index']] = 'palace'; nk += 1; names_.append('%d:%s' % (v_['pass_index'], n_.split('경복궁_')[-1]))
    bad_ = [i_.filepath for i_ in bpy.data.images if i_ not in img0_ and i_.source == 'FILE' and not os.path.exists(bpy.path.abspath(i_.filepath))]
    if bad_: raise RuntimeError('KHS 텍스처 경로 미해결 %d: %s' % (len(bad_), bad_[:3]))
    print('khs models', nk, names_, flush=True)

# ---------- 공개 장면: 국가유산청 전각 자리(모델은 넣지 않고 OSM 대체 모형에 표시만) ----------
# KHS 를 켠 렌더(KPL)에서 빠졌을 오브젝트 = 같은 규칙(덮임 50% 초과, osm_k, 지붕 속 나무)으로 고른 대체 모형. insert_khs.py 가 이 표시를 읽어 바꿔 끼운다.
SLOTF = os.environ.get('P3D_KHS_SLOTS', '')
SLOTS = json.load(open(SLOTF))['models'] if SLOTF and not KPL and os.path.exists(SLOTF) else {}
SFP = {n_: unary_union([Polygon(c_).buffer(0) for c_ in v_['footprint']]) for n_, v_ in SLOTS.items()}
if SLOTS:
    KSUN = Euler((math.radians(50), 0, math.radians(-28))).to_matrix() @ Vector((0, 0, -1))
    SLOTS = {n_: v_ for n_, v_ in SLOTS.items() if khs_inwin(SFP[n_], v_['zmax'])}; SFP = {n_: SFP[n_] for n_ in SLOTS}
SFP_ALL = unary_union(list(SFP.values())) if SLOTS else None
SFP_B = unary_union([g_ for n_, g_ in SFP.items() if not SLOTS[n_].get('keep_trees')]) if SLOTS else None
SSKIPK = {k_: n_ for n_, v_ in SLOTS.items() for k_ in v_.get('osm_k', [])}
KGEO_SLOT = json.load(open(os.environ['P3D_KHS_GEO']))['khs'] if os.environ.get('P3D_KHS_GEO') and os.path.exists(os.environ['P3D_KHS_GEO']) else None
def slot_of(p, k=None):
    if k is not None and k in SSKIPK: return SSKIPK[k]
    if not SLOTS or p.is_empty or p.area <= 0 or not SFP_ALL.intersects(p): return None
    if SFP_ALL.intersection(p).area / p.area <= 0.5: return None
    return max(SFP, key=lambda n_: SFP[n_].intersection(p).area)
def slot_tree(x_, y_):
    if not SLOTS or SFP_B is None or not SFP_B.contains(Point(x_, y_)): return None
    return next((n_ for n_, g_ in SFP.items() if not SLOTS[n_].get('keep_trees') and g_.contains(Point(x_, y_))), None)
SLOT_COLS = {}
def slot_key(name): return 'gwanghwamun' if name == 'gwanghwamun' else 'slot%d' % SLOTS[name]['pass_index']
def tag(mark, name, why):
    if name is None: return
    key = slot_key(name)
    if key not in SLOT_COLS:
        top_ = bpy.data.collections.get('KHS_STANDIN') or bpy.data.collections.new('KHS_STANDIN')
        if top_.name not in sc.collection.children: sc.collection.children.link(top_)
        SLOT_COLS[key] = bpy.data.collections.new(key); top_.children.link(SLOT_COLS[key])
    for o_ in CREATED[mark:]:
        o_['khs_slot'] = key; o_['khs_standin'] = why; o_.name = key + '_' + o_.name
        for c_ in list(o_.users_collection): c_.objects.unlink(o_)
        SLOT_COLS[key].objects.link(o_)

# ---------- 장면 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; META = {1: 'ground'}
blds = json.load(open(R + 'hires/derived-data/city_buildings.json'))['buildings']
n = 0
for i, b in enumerate(blds):
    c = np.mean(np.array(b['rings'][0]), 0)
    if not inwin(c, b['h']): continue
    if KPL and khs_cov(Polygon(b['rings'][0]).buffer(0)) > 0.5: continue  # KHS 전각이 대신 선다
    mk = len(CREATED)
    if b['type'] == 'hanok_roof_inferred':
        roofed(Polygon(b['rings'][0], b['rings'][1:]), 10000 + i, b['seed'], 'hanok', min(3.4, max(2.7, b['h'] - 1.0))); META[10000 + i] = 'hanok'
    else: modern(b, 10000 + i); META[10000 + i] = b['type']
    if SLOTS: tag(mk, slot_of(Polygon(b['rings'][0]).buffer(0)), 'city_building')
    n += 1
print('city buildings', n, flush=True)

sys.path.insert(0, HERE); import osm_blds
have = STRtree([Polygon(b['rings'][0]).buffer(0) for b in blds]); hv = have.geometries
raw = json.load(open(R + 'osm_raw.json'))['elements']
pal = [e for e in raw if e['type'] == 'relation' and e['id'] == 5501517]; palpoly = None
if pal:
    ls = [LineString([osm_blds.tm5186(q['lon'], q['lat']) for q in m_['geometry']]) for m_ in pal[0]['members'] if m_.get('geometry') and m_.get('role') in ('outer', '')]
    pp = list(polygonize(unary_union(ls))); palpoly = unary_union(pp) if pp else None
PMETA = {v['osm_way']: v for k, v in json.load(open(R + 'hires/ids/id_map.json'))['ids'].items() if v.get('kind') == 'palace_building'}
kinds = np.asarray(Image.open(R + 'keep/guide6/guide_kinds.png'))
KHS = os.environ.get('P3D_KHS', ROOT + 'khs/'); USE_KHS = os.path.exists(KHS + 'SM_GwanghwamunComplex.fbx')
KGEO = json.load(open(KHS + 'scene_geometry.json'))['khs'] if USE_KHS else None; KG = (KGEO['tx_local'], KGEO['ty_local'], 0.0) if USE_KHS else (0, 0, 0)
GATES = {'광화문': (7.0, True), '건춘문': (4.6, False), '신무문': (4.2, False), '영추문': (4.6, False), '동십자각': (5.0, False)}
TWO = ('근정전', '경회루', '흥례문', '근정문')
m = 0
for k, e in enumerate(raw):
    t = e.get('tags', {})
    if e['type'] != 'way' or ('building' not in t and 'building:part' not in t) or not e.get('geometry') or len(e['geometry']) < 4: continue
    ring = np.array([osm_blds.tm5186(q['lon'], q['lat']) for q in e['geometry']]); p = orient(Polygon(ring).buffer(0), 1.0)
    if p.geom_type != 'Polygon' or p.area < 4: continue
    cen = p.centroid.coords[0]
    if not inwin(cen, 30): continue
    if any(hv[i].intersection(p).area > 0.3 * p.area for i in have.query(p)): continue
    if KPL and (k in KSKIPK or khs_cov(p) > 0.5): continue  # KHS 전각이 대신 선다
    idn = 12000 + k; seed = 7000 + k; name = t.get('name', '') or PMETA.get(e['id'], {}).get('name', ''); pm = PMETA.get(e['id'])
    if name == '광화문' and USE_KHS: continue  # 국가유산청 모델로 대체
    mk = len(CREATED); sl = 'gwanghwamun' if (name == '광화문' and KGEO_SLOT) else (slot_of(p, k) if SLOTS else None)
    gk = next((g for g in GATES if g in name), None)
    if gk: gate(p, idn, seed, *GATES[gk]); META[idn] = 'palace'
    elif (palpoly is not None and palpoly.contains(p.centroid) and not (pm and pm.get('type') == 'modern')) or t.get('historic') or t.get('building') in ('temple', 'shrine', 'pavilion'):
        hm = pm['h_m'] if pm else 3.7; two = bool(pm and pm.get('double_roof')) or any(x in name for x in TWO)
        isgate = name.endswith('문') or t.get('building') == 'gatehouse'
        roofed(p, idn, seed, 'palace', 3.0 + (hm - 3.7) * 0.6 if t.get('building') != 'roof' else 2.7, 0.0, 'hip' if isgate else None, two,
               platform=None if (p.area < 30 or isgate) else ([(7.0, 1.3), (3.2, 1.3)] if p.area > 600 else (1.4, 0.6)))
        META[idn] = 'palace'
    else:
        px_, py_ = proj([cen[0], cen[1], 0]); kd = int(kinds[min(kinds.shape[0] - 1, max(0, int(py_ // 8))), min(kinds.shape[1] - 1, max(0, int(px_ // 8)))])
        lv = t.get('building:levels'); rr = random.Random(seed)
        if kd == 2 or (t.get('building') == 'house' and p.area < 140 and kd in (0, 1, 2)) and rr.random() < 0.5:
            roofed(p, idn, seed, 'hanok', 2.9); META[idn] = 'hanok'
        else:
            fl = int(float(lv)) if lv and lv.replace('.', '', 1).isdigit() else {3: rr.choice([3, 4, 5]), 4: rr.choice([12, 15, 18]), 5: rr.choice([9, 12]), 6: 3}.get(kd, rr.choice([1, 2, 2, 3, 3, 4]))
            fac = {3: 'office_stone', 4: 'curtain_glass', 5: 'resi_tower', 6: 'civic_stone'}.get(kd) or rr.choice(['brick', 'stucco', 'stucco'])
            modern({'rings': [[tuple(q) for q in ring]], 'h': fl * 3.3, 'seed': seed, 'fac': fac, 'flh': 3.3, 'storefront': rr.random() < .3, 'parapet': True, 'penthouse': rr.random() < .25,
                    'roofcol': rr.choice(['roof_green', 'roof_green', 'roof_concrete', 'roof_dark'])}, idn); META[idn] = 'tower' if fl >= 9 else 'lowrise'
    if sl: tag(mk, sl, 'osm_building')
    m += 1
print('osm buildings', m, flush=True)

# 광화문·월대·해태: 국가유산청 3D 기록(공공누리 제1유형, 출처: 국가유산청). 원본 파일은 재배포 금지 → 렌더에만 쓴다.
if USE_KHS and inwin(KG, 20, 900):
    import addon_utils; addon_utils.enable('io_scene_fbx')
    before = set(bpy.data.objects); bpy.ops.import_scene.fbx(filepath=KHS + 'SM_GwanghwamunComplex.fbx', use_anim=False)
    new = [o for o in bpy.data.objects if o not in before]
    tex = {p.lower(): KHS + 'tex1024/' + p for p in os.listdir(KHS + 'tex1024')}
    for img in bpy.data.images:
        if img.source != 'FILE': continue
        stem = os.path.splitext(os.path.basename(img.filepath or img.name).lower())[0]; stem2 = stem.split('_lod')[0]; cand = None
        for s_ in (stem, stem2):
            for k_, v_ in tex.items():
                if os.path.splitext(k_)[0] == s_: cand = v_
        if cand is None:
            for key in ('haetaea', 'haetaeb'):
                if key in stem: cand = tex.get('t_ghm_%s%s.png' % (key, '_n' if stem.endswith('_n') else ('_r' if stem.endswith('_r') else '_bc')))
        if cand: img.filepath = cand; img.reload()
    for m_ in bpy.data.materials:
        if not m_.name.startswith('M_GHM') or not m_.use_nodes: continue
        bs = [n_ for n_ in m_.node_tree.nodes if n_.type == 'BSDF_PRINCIPLED']
        if not bs: continue
        inp = bs[0].inputs['Base Color']; flat = {'M_GHM_Grass': '#5fb043', 'M_GHM_Ground02A1': '#d8ccb2', 'M_GHM_Ground01A': '#d4c7aa', 'M_GHM_Road': '#cdbfa4'}.get(m_.name)
        if flat:
            for l_ in list(inp.links): m_.node_tree.links.remove(l_)
            inp.default_value = lin(flat)
    root = bpy.data.objects.new('KHS_ROOT', None); sc.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
        if o.type == 'MESH': o.pass_index = 1 if 'Ground' in o.name else 2  # KHS 지면은 지면 ID
    root.rotation_euler = (0, 0, math.radians(KGEO['theta_deg'])); root.location = (KG[0], KG[1], 0.03)
    META[2] = 'khs'; print('KHS', sorted(o.name for o in new if o.type == 'MESH'), flush=True)
if KPL: khs_place()
BRIDGE_SRC = KPL or SLOTS  # 공개 장면에서도 돌다리는 세운다(국가유산청 모델이 아니라 이 스크립트가 만드는 것)
if GV2 and BRIDGE_SRC:  # 3차: 배치 항목의 돌다리(지도 좌표 p0→p1, 폭 w, 윗면 높이 z0→z1 경사, 두께 0.5 m, 양쪽 난간 0.3×0.45 m). 섬 모델 pass_index 로 묶는다.
    def _prism(mb_, a_, b_, w_, za_, zb_, th_, m_):
        d_ = np.subtract(b_, a_); d_ = d_ / np.linalg.norm(d_); n_ = np.array([-d_[1], d_[0]]) * w_ / 2
        top_ = [(*(np.add(a_, -n_)), za_), (*(np.add(b_, -n_)), zb_), (*(np.add(b_, n_)), zb_), (*(np.add(a_, n_)), za_)]
        bot_ = [(x_, y_, z_ - th_) for x_, y_, z_ in top_]
        mb_.face(top_, m_); mb_.face(bot_[::-1], m_)
        for k_ in range(4): mb_.face([bot_[k_], bot_[(k_ + 1) % 4], top_[(k_ + 1) % 4], top_[k_]], m_)
    nb_ = 0
    for n_, v_ in BRIDGE_SRC.items():
        for b_ in v_.get('bridges', []):
            mb_ = MB(); p0_, p1_ = np.array(b_['p0']), np.array(b_['p1']); d_ = (p1_ - p0_) / np.linalg.norm(p1_ - p0_); nn_ = np.array([-d_[1], d_[0]])
            _prism(mb_, p0_, p1_, b_['w'], b_['z0'], b_['z1'], 0.5, mat_flat('#bdb6a6'))
            for sg_ in (-1, 1):  # 난간
                o_ = nn_ * sg_ * (b_['w'] / 2 - 0.15)
                _prism(mb_, p0_ + o_, p1_ + o_, 0.3, b_['z0'] + 0.45, b_['z1'] + 0.45, 0.45, mat_flat('#d2ccbe'))
            mb_.build('khs_bridge_%d_%d' % (v_['pass_index'], nb_), v_['pass_index']); nb_ += 1
    print('khs bridges', nb_, flush=True)

wl = 0
for wi, e in enumerate(json.load(open(R + 'osm_walls.json'))['elements']):
    if e['type'] != 'way' or e.get('tags', {}).get('barrier') not in ('wall', 'city_wall'): continue
    pts = [osm_blds.tm5186(q['lon'], q['lat']) for q in e['geometry']]
    if len(pts) < 2: continue
    ln = LineString(pts); nseg = max(1, int(math.ceil(ln.length / 12.0))); hh = 2.6 if e['tags']['barrier'] == 'wall' else 4.0
    for si in range(nseg):
        part = substring(ln, max(0, si * ln.length / nseg - 0.3), min(ln.length, (si + 1) * ln.length / nseg + 0.3))
        if part.length < 0.3 or not (inwin(part.coords[0]) or inwin(part.coords[-1])): continue
        if KPL and khs_cov(part.buffer(0.45, cap_style=2, join_style=2)) > 0.5: continue  # KHS 모델의 담·문 구간
        mk = len(CREATED)
        roofed(part.buffer(0.45, cap_style=2, join_style=2), 21000 + wi, e['id'] % 9973, 'wall', hh); META[21000 + wi] = 'wall'; wl += 1
        if SLOTS: tag(mk, slot_of(part.buffer(0.45, cap_style=2, join_style=2)), 'wall')
print('wall pieces', wl, flush=True)

tn = 0
for (tid, tx, ty, tw_, th_, cnt) in json.load(open(f'{HERE}/trees_px_v2.json' if GV2 else f'{HERE}/trees_px.json')):
    r = max(1.4, min(4.5, tw_ * PX / 2)); g = unproj(tx, ty, 2.2 + r * 0.9)
    if not inwin(g, 8): continue
    if KPL and KFP_B is not None and KFP_B.contains(Point(g[0], g[1])): continue  # KHS 전각 지붕 속 나무
    mk = len(CREATED); tree(tid, g[0], g[1], r); META[22000 + tid] = 'tree'; tn += 1
    if SLOTS: tag(mk, slot_tree(g[0], g[1]), 'tree')
print('trees', tn, flush=True)

M = 1400; OUTS = OUT.replace('/', '_')
gbox = (max(0, X0 - M), max(0, Y0 - M), min(W, X0 + WW + M), min(H, Y0 + WH + M))
Image.MAX_IMAGE_PIXELS = None; Image.open(f'{HERE}/ground_clean_v2.png' if GV2 else f'{HERE}/ground_clean.png').crop(gbox).save(f'{HERE}/tmp_ground_{OUTS}.png')
mb = MB(); gm = mat_tex(f'{HERE}/tmp_ground_{OUTS}.png', 'ground')
mb.face([unproj(gbox[0], gbox[3]), unproj(gbox[2], gbox[3]), unproj(gbox[2], gbox[1]), unproj(gbox[0], gbox[1])], gm, [(0, 0), (1, 0), (1, 1), (0, 1)])
mb.build('ground', 1)

cd = bpy.data.cameras.new('cam'); cd.type = 'ORTHO'; cd.ortho_scale = max(WW, WH) * PX; cd.clip_start = 1; cd.clip_end = 6000
co = bpy.data.objects.new('cam', cd); sc.collection.objects.link(co); sc.camera = co
co.rotation_euler = (math.radians(55), 0, math.radians(45))
co.location = Vector(CL + EX * ((X0 + WW / 2 - W / 2) * PX) + EY * (-(Y0 + WH / 2 - H / 2) * PX))
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 3.6; sd.angle = math.radians(1.5)
so = bpy.data.objects.new('sun', sd); so.rotation_euler = (math.radians(50), 0, math.radians(-28)); sc.collection.objects.link(so)
w = bpy.data.worlds.new('w'); w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (1, 1, 1, 1); bg.inputs[1].default_value = 0.7; sc.world = w
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(os.environ.get('P3D_SPP', 64)); sc.cycles.use_denoising = False; sc.cycles.filter_width = 0.6
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = WW, WH, 100
sc.view_settings.view_transform = 'Standard'; sc.render.image_settings.file_format = 'PNG'
os.makedirs(os.path.dirname(f'{HERE}/{OUT}') or '.', exist_ok=True)
sc.render.filepath = f'{HERE}/{OUT}.png'
print('scene built', flush=True)
if SAVE_BLEND:
    from mathutils import Euler as _E
    scol = None
    def _slot_empty(key, props, loc, theta):
        global scol
        if scol is None: scol = bpy.data.collections.new('KHS_SLOTS'); sc.collection.children.link(scol)
        e_ = bpy.data.objects.new(key, None); e_.empty_display_type = 'ARROWS'; e_.empty_display_size = 6.0
        e_.location = loc; e_.rotation_euler = (0, 0, math.radians(theta)); scol.objects.link(e_)
        for k_, v_ in props.items(): e_[k_] = v_ if isinstance(v_, (int, float, str, bool)) else json.dumps(v_, ensure_ascii=False)
        e_['standin_objects'] = len(SLOT_COLS[key].objects) if key in SLOT_COLS else 0
    for n_, v_ in SLOTS.items():
        _slot_empty(slot_key(n_), dict(khs_model=n_, pass_index=v_['pass_index'], theta=v_['theta'], tx=v_['tx'], ty=v_['ty'], tz=v_.get('tz', 0.0), grade=v_.get('grade', ''),
                    keep_trees=bool(v_.get('keep_trees')), has_ground=bool(v_.get('has_ground')), osm_k=v_.get('osm_k', []),
                    source='국가유산청 경복궁 3D 기록(digital.khs.go.kr), 공공누리 제1유형 — 이 파일에는 들어 있지 않음'), (v_['tx'], v_['ty'], v_.get('tz', 0.0)), v_['theta'])
    if KGEO_SLOT and 'gwanghwamun' in SLOT_COLS:
        _slot_empty('gwanghwamun', dict(khs_model='광화문 3D 기록(SM_GwanghwamunComplex.fbx)', pass_index=2, theta=KGEO_SLOT['theta_deg'], tx=KGEO_SLOT['tx_local'], ty=KGEO_SLOT['ty_local'], tz=0.03,
                    source='국가유산청 광화문 3D 기록(digital.khs.go.kr), 공공누리 제1유형 — 이 파일에는 들어 있지 않음'), (KGEO_SLOT['tx_local'], KGEO_SLOT['ty_local'], 0.03), KGEO_SLOT['theta_deg'])
    sys.path.insert(0, os.path.join(HERE, '..', 'common')); import blend_save
    blend_save.save(SAVE_BLEND, dict(map='gyeongbokgung', window_px=[X0, Y0, WW, WH], px_m=PX, canvas_px=[W, H], samples=sc.cycles.samples,
                    slots=sorted(SLOT_COLS), meta=META), readme=open(os.path.join(HERE, '..', 'common', 'BLEND-README.md'), encoding='utf-8').read())
    if NO_RENDER:
        try: os.remove(f'{HERE}/tmp_ground_{OUTS}.png')
        except OSError: pass
        sys.exit(0)
bpy.ops.render.render(write_still=True)
json.dump(META, open(f'{HERE}/{OUT}_meta.json', 'w'))
if os.environ.get('P3D_PASS', '1') == '1':  # ID(R=상위, G=하위 바이트)·깊이(2040 + v×0.025 m, 16비트를 R,G 로) 패스
    def ovr(name, build):
        mt = bpy.data.materials.new(name); mt.use_nodes = True; nt = mt.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(em.outputs[0], out.inputs[0])
        v = build(nt)
        def mnode(op, a, b_):
            n_ = nt.nodes.new('ShaderNodeMath'); n_.operation = op
            for i_, s_ in enumerate((a, b_)):
                if s_ is None: continue
                if isinstance(s_, (int, float)): n_.inputs[i_].default_value = s_
                else: nt.links.new(s_, n_.inputs[i_])
            return n_.outputs[0]
        hi = mnode('FLOOR', mnode('DIVIDE', v, 256.0), None); lo = mnode('SUBTRACT', v, mnode('MULTIPLY', hi, 256.0))
        cmb = nt.nodes.new('ShaderNodeCombineColor'); nt.links.new(mnode('DIVIDE', hi, 255.0), cmb.inputs[0]); nt.links.new(mnode('DIVIDE', lo, 255.0), cmb.inputs[1]); cmb.inputs[2].default_value = 0
        nt.links.new(cmb.outputs[0], em.inputs[0]); return mt
    def b_id(nt): return nt.nodes.new('ShaderNodeObjectInfo').outputs['Object Index']
    def b_z(nt):
        cdn = nt.nodes.new('ShaderNodeCameraData'); a = nt.nodes.new('ShaderNodeMath'); a.operation = 'SUBTRACT'; nt.links.new(cdn.outputs['View Z Depth'], a.inputs[0]); a.inputs[1].default_value = 2040.0
        d_ = nt.nodes.new('ShaderNodeMath'); d_.operation = 'DIVIDE'; nt.links.new(a.outputs[0], d_.inputs[0]); d_.inputs[1].default_value = 0.025
        r_ = nt.nodes.new('ShaderNodeMath'); r_.operation = 'ROUND'; nt.links.new(d_.outputs[0], r_.inputs[0]); return r_.outputs[0]
    sc.cycles.samples = 1; sc.cycles.filter_width = 0.01; sc.view_settings.view_transform = 'Raw'; bg.inputs[1].default_value = 0.0; so.hide_render = True
    sc.cycles.max_bounces = 0; sc.render.dither_intensity = 0.0
    for nm, bf in (('id', b_id), ('z', b_z)):
        sc.view_layers[0].material_override = ovr(nm, bf); sc.render.filepath = f'{HERE}/{OUT}_{nm}.png'; bpy.ops.render.render(write_still=True)
try: os.remove(f'{HERE}/tmp_ground_{OUTS}.png')
except OSError: pass
print('done', flush=True)
