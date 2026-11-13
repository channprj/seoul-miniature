# 여의도 판(임의 지역) 생성기. 아래 "gen.py 복사" 구간은 gyeongbokgung/gen.py(2026-11-11 12:33 판) 의 빌더를 그대로 복사한 것이다.
# gen.py 는 고치지 않는다. 바뀐 곳: tree() 가 공유 메시 조립기(mb)에 붙도록 한 것, walls() 가 곡면 구간(ring_runs)을 따르게 한 것.
# ===== gen.py 복사 시작 =====
import sys, json, math, random, os
import numpy as np
import bpy
from mathutils import Vector
from PIL import Image, ImageDraw
import shapely
from shapely.geometry import Polygon, Point
from shapely.geometry.polygon import orient

HERE = os.path.dirname(os.path.abspath(__file__))
import tempfile, atexit, shutil; TEXD = tempfile.mkdtemp(prefix='p3dtex_'); atexit.register(lambda: shutil.rmtree(TEXD, ignore_errors=True))  # 프로세스별 텍스처 폴더(병렬 쓰기 경합 방지)
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
        me.update(); o = bpy.data.objects.new(name, me); o.pass_index = idx; bpy.context.scene.collection.objects.link(o); return o

def ring_runs(coords, ang=28.0):
    """[여의도판 추가] 닫힌 고리를 '곡면 구간'으로 나눈다: 이웃 변의 꺾임이 ang° 미만이면 한 구간. 반환: 점 목록들(각 구간 폴리라인)."""
    c = [tuple(p) for p in coords[:-1]]; n = len(c)
    if n < 3: return [list(coords)]
    def turn(i):
        p, q, r = np.array(c[i - 1]), np.array(c[i]), np.array(c[(i + 1) % n]); u, v = q - p, r - q
        nu, nv = np.hypot(*u), np.hypot(*v)
        if nu < 1e-6 or nv < 1e-6: return 0.0
        return math.degrees(math.acos(max(-1, min(1, (u @ v) / (nu * nv)))))
    sharp = [i for i in range(n) if turn(i) >= ang]
    if not sharp: return [c + [c[0]]]
    out = []
    for k, i in enumerate(sharp):
        j = sharp[(k + 1) % len(sharp)]; seq = [c[i]]; t = i
        while True:
            t = (t + 1) % n; seq.append(c[t])
            if t == j: break
        out.append(seq)
    return out
def _arc(seq):
    s = [0.0]
    for p, q in zip(seq[:-1], seq[1:]): s.append(s[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    return s
def _sub(seq, s, s0, s1):
    """구간 [s0,s1] 의 폴리라인 점들(호 길이 포함)."""
    def at(t):
        for k in range(len(s) - 1):
            if s[k + 1] >= t: f = (t - s[k]) / max(s[k + 1] - s[k], 1e-9); return (seq[k][0] + (seq[k + 1][0] - seq[k][0]) * f, seq[k][1] + (seq[k + 1][1] - seq[k][1]) * f)
        return seq[-1]
    pts = [(at(s0), s0)] + [(seq[k], s[k]) for k in range(len(s)) if s0 < s[k] < s1] + [(at(s1), s1)]
    return pts

def walls(mb, poly, z0, z1, kind, store, seed, flh, bay=None):
    """[여의도판에서 바꿈] gen.py 의 walls() 와 같은 텍스처·칸 규칙이되, 변 대신 '곡면 구간'(ring_runs)의 호 길이로 칸을 나눈다.
    곡선 벽(OSM 의 짧은 변 여러 개)이 빈 벽 띠로 끊기지 않고, 칸 하나가 곡선을 따라 여러 면으로 휜다."""
    bay = bay or BAY
    tex = mat_tex(facade_tex(kind), 'tex_' + kind); rnd = random.Random(seed)
    nfl = max(1, round((z1 - z0) / flh)); fh = (z1 - z0) / nfl
    for ring in [poly.exterior] + list(poly.interiors):
        for seq in ring_runs(list(ring.coords)):
            s = _arc(seq); L = s[-1]
            if L < 0.05: continue
            nb = max(1, round(L / bay)) if L >= 2.2 else 1
            for k in range(nb):
                pts = _sub(seq, s, L * k / nb, L * (k + 1) / nb); sa, sb = pts[0][1], pts[-1][1]
                for f in range(nfl):
                    col = 4 if L < 2.2 else rnd.choice([0, 0, 0, 1, 2, 3] if not (store and f == 0) else [0, 1, 2, 3])
                    if kind not in ('hanok', 'palace', 'wall') and kind not in OFFICE and L >= 2.2 and rnd.random() < 0.12: col = 4
                    row = 1 if (store and f == 0 and kind != 'hanok') else 0
                    u0, u1 = col / 5, (col + 1) / 5; v1 = 1 - row / 2; v0 = v1 - 0.5
                    za, zb = z0 + f * fh, z0 + (f + 1) * fh
                    for (p, sp), (q, sq) in zip(pts[:-1], pts[1:]):
                        if math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-4: continue
                        ua, ub = u0 + (u1 - u0) * (sp - sa) / max(sb - sa, 1e-9), u0 + (u1 - u0) * (sq - sa) / max(sb - sa, 1e-9)
                        mb.face([(p[0], p[1], za), (q[0], q[1], za), (q[0], q[1], zb), (p[0], p[1], zb)], tex, [(ua, v0), (ub, v0), (ub, v1), (ua, v1)])
                    if row == 1 and col != 4 and rnd.random() < 0.6 and len(pts) == 2:  # 차양(곧은 칸만)
                        p, q = pts[0][0], pts[-1][0]; Lc = math.hypot(q[0] - p[0], q[1] - p[1]) or 1
                        nx, ny = (q[1] - p[1]) / Lc, -(q[0] - p[0]) / Lc; am = mat_flat(rnd.choice(AWN[:5]))
                        mb.face([(p[0], p[1], za + 2.75), (q[0], q[1], za + 2.75), (q[0] + nx * .8, q[1] + ny * .8, za + 2.3), (p[0] + nx * .8, p[1] + ny * .8, za + 2.3)], am)

ROOF = {'roof_green': '#58a17d', 'roof_concrete': '#a5a39c', 'roof_dark': '#4a4d55', 'roof_tile': '#b4664a'}
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

def blob(mb, c, r, m, sq=1.0, n=7):
    rings = [(0, -1)] + [(math.cos(a), math.sin(a)) for a in (-0.6, 0.15, 0.85)] + [(0, 1)]
    prev = None
    for cr, sr in rings:
        ring = [(c[0] + r * cr * math.cos(2 * math.pi * k / n), c[1] + r * cr * math.sin(2 * math.pi * k / n), c[2] + r * sq * sr) for k in range(n)]
        if prev:
            for k in range(n): mb.face([prev[k], prev[(k + 1) % n], ring[(k + 1) % n], ring[k]], m)
        prev = ring

GREENS = ['#4f8f3f', '#5a9a45', '#3f7d3a', '#6aa84e', '#467f48']
def tree(i, x, y, r, mb):
    rnd = random.Random(900 + i); pine = rnd.random() < 0.28; th = 1.8 + r * 0.5
    mb.cyl((x, y, 0), 0.16 + r * 0.04, th + (r if pine else 0.3), mat_flat('#6b4b34'), n=6)
    if pine:
        g = mat_flat(rnd.choice(['#2f6b3d', '#356f43', '#2a6038']))
        for k in range(3): mb.cyl((x + rnd.uniform(-.3, .3), y + rnd.uniform(-.3, .3), th + k * r * .45), r * (1.0 - k * .27), r * .35, g, mat_flat('#3f7d4a'), n=8)
    else:
        g = [mat_flat(c) for c in rnd.sample(GREENS, 2)]
        blob(mb, (x, y, th + r * .75), r, g[0], 0.85)
        for k in range(rnd.randrange(1, 4)):
            a = rnd.uniform(0, 6.28); blob(mb, (x + math.cos(a) * r * .55, y + math.sin(a) * r * .55, th + r * rnd.uniform(.5, 1.1)), r * rnd.uniform(.5, .7), g[k % 2], 0.85)
# ===== gen.py 복사 끝 =====

# ================= 여의도 판: OSM 만으로 임의 지역을 만든다 =================
# 사용: venv/bin/python gen_area.py <판 A|B|C|F> <X0> <Y0> <출력 접두어> [--save-blend <경로.blend>] [--no-render]
#   --save-blend: 세운 장면(카메라·해·툰 재질·텍스처 포함)을 렌더 직전 상태로 저장한다(../common/blend_save.py). --no-render: 저장만 하고 끝낸다.
#   X0,Y0 = 판의 6.25 cm 캔버스 좌표(창 왼쪽 위). 환경변수: P3D_W/P3D_H(렌더 px, 기본 1408×1024), P3D_PXR(렌더 m/px, 기본 0.0625;
#   미리보기는 0.5), P3D_SPP(기본 64), P3D_PASS(1=ID·깊이 패스), P3D_GTEX(지면 텍셀 m, 기본 PXR×0.8)
# 출력: <출력>.png, _id.png(R·256+G = pass_index), _z.png(깊이 = z0 + v·step, meta 에 기록), _meta.json
import zlib, time
from shapely.geometry import LineString, box, MultiPolygon
from shapely.ops import unary_union, substring
from shapely.strtree import STRtree
from PIL import ImageColor
AREA = os.environ.get('P3D_AREA', HERE)   # 다른 지역: 그 지역의 cam.py·lm_build.py 가 있는 폴더(예: ../teheran). 장면 자료는 P3D_SCENE(기본 AREA/scene.json)
sys.path.insert(0, AREA); from cam import Cam, PX as PX0
T0 = time.time()
SAVE_BLEND, NO_RENDER = None, False
if '--save-blend' in sys.argv: _i = sys.argv.index('--save-blend'); SAVE_BLEND = sys.argv[_i + 1]; del sys.argv[_i:_i + 2]
if '--no-render' in sys.argv: sys.argv.remove('--no-render'); NO_RENDER = True
BOARD, X0, Y0, OUT = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
CAM = Cam(BOARD); EX, EY, VD = CAM.EX, CAM.EY, CAM.VD
PXR = float(os.environ.get('P3D_PXR', PX0)); WW, WH = int(os.environ.get('P3D_W', 1408)), int(os.environ.get('P3D_H', 1024))
SC = PXR / PX0; WX1, WY1 = X0 + WW * SC, Y0 + WH * SC
GTEX = float(os.environ.get('P3D_GTEX', PXR * 0.8)); FINE = GTEX <= 0.15
S = json.load(open(os.environ.get('P3D_SCENE', AREA + '/scene.json')))
META = {1: 'ground'}
bpy.ops.wm.read_factory_settings(use_empty=True)

# [3차] 해(아래 카메라 절의 sun: 오일러 (50°, 0, θ−73°)) 의 그림자 수평 이동량(높이 1 m 당). 창 밖 물체의 그림자도 창 안에 드리우므로
#   컬링 판정에 그림자 끝점을 넣는다(전체 타일 렌더에서 이웃 타일 사이 그림자 단차가 났음).
_sa, _sg = math.radians(50.0), math.radians(CAM.b['theta'] - 73.0)
SHX, SHY = -math.sin(_sg) * math.tan(_sa), math.cos(_sg) * math.tan(_sa)
def inwin(c, h=3.0, r=10.0):
    xs_, ys_ = zip(*(CAM.proj(p_) for p_ in ([c[0], c[1], 0], [c[0], c[1], h], [c[0] + SHX * h, c[1] + SHY * h, 0]))); mg = (r + 4) / PX0
    return max(xs_) + mg > X0 and min(xs_) - mg < WX1 and max(ys_) + mg > Y0 and min(ys_) - mg < WY1
def parts(g):
    if g is None or g.is_empty: return []
    if g.geom_type == 'Polygon': return [g]
    return [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']
def P(rings): return Polygon(rings[0], rings[1:]).buffer(0)

def mrr_axes(poly):
    mc = np.array(poly.minimum_rotated_rectangle.exterior.coords); e0, e1 = mc[1] - mc[0], mc[2] - mc[1]
    if np.hypot(*e0) < np.hypot(*e1): e0, e1 = e1, e0
    return np.array(poly.centroid.coords[0]), e0 / np.hypot(*e0), np.hypot(*e0), np.hypot(*e1), mc[:4]
# ---------- 지면: OSM 을 평면 텍스처로 직접 그린다(분류 래스터 → 팔레트 + 월드 고정 잡음 → 노면 표시) ----------
GM = 60.0 if not FINE else 45.0
gcorn = [CAM.unproj(X, Y, 0) for X, Y in ((X0, Y0), (WX1, Y0), (WX1, WY1), (X0, WY1))]
GREG = Polygon([c[:2] for c in gcorn]).buffer(GM, join_style=2)
gx0, gy0, gx1, gy1 = GREG.bounds
gx0, gy1 = math.floor(gx0 / GTEX) * GTEX, math.ceil(gy1 / GTEX) * GTEX  # [3차] 텍셀 격자를 월드에 고정(타일마다 같은 격자 → 이음매에서 서브텍셀 어긋남 없음)
GWp, GHp = int(math.ceil((gx1 - gx0) / GTEX)), int(math.ceil((gy1 - gy0) / GTEX))
gx1, gy0 = gx0 + GWp * GTEX, gy1 - GHp * GTEX
GBOX = box(gx0, gy0, gx1, gy1)
Image.MAX_IMAGE_PIXELS = None
CLS = Image.new('L', (GWp, GHp), 0); CD = ImageDraw.Draw(CLS)
def tp(pts): return [((x - gx0) / GTEX, (gy1 - y) / GTEX) for x, y in pts]
def fillg(g, val, img=None):
    img = img or CLS
    for p in parts(g.intersection(GBOX) if not GBOX.contains(g) else g):
        if p.area < GTEX * GTEX: continue
        bx0, by0, bx1, by1 = p.bounds; X_0, Y_0 = int((bx0 - gx0) / GTEX), int((gy1 - by1) / GTEX); X_1, Y_1 = int((bx1 - gx0) / GTEX) + 2, int((gy1 - by0) / GTEX) + 2
        m = Image.new('1', (X_1 - X_0, Y_1 - Y_0), 0); dm = ImageDraw.Draw(m)
        sh = lambda pts: [(u - X_0, v - Y_0) for u, v in tp(pts)]
        dm.polygon(sh(p.exterior.coords), fill=1)
        for r in p.interiors: dm.polygon(sh(r.coords), fill=0)
        img.paste(val, (X_0, Y_0, X_1, Y_1), m)
def lineg(ln, w, val, d=None):
    d = d or CD
    g = ln.intersection(GBOX.buffer(w))
    for q in ([g] if g.geom_type == 'LineString' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'LineString']):
        if q.length > 0: d.line(tp(q.coords), fill=val, width=max(1, int(round(w / GTEX))), joint='curve')
# 분류 번호와 팔레트(색, 잡음 세기)
GC = {0: ('#cfc9bd', .05), 1: ('#d3cdbf', .05), 2: ('#cdc8bf', .04), 3: ('#8fbe63', .05), 4: ('#6a9d4c', .07), 5: ('#5d8fbd', .05), 6: ('#5f95b8', .04), 7: ('#e1d3a8', .06),
      8: ('#5ea552', .05), 9: ('#c98a5a', .05), 10: ('#a9a8a2', .04), 11: ('#b79c76', .08), 12: ('#968e83', .10), 13: ('#dcd5c8', .04), 14: ('#5e6268', .04), 15: ('#74777c', .04),
      16: ('#d8c6a2', .05), 17: ('#ae6f5f', .04), 18: ('#a88d68', .06), 19: ('#b5b1a6', .05), 20: ('#c4c0b6', .03),
      21: ('#d9d3c6', .03), 22: ('#58c3d3', .03), 23: ('#a3ad66', .10), 24: ('#97c76c', .04), 25: ('#8f8a7e', .14), 26: ('#c9c4b6', .03), 27: ('#8a7a62', .05), 28: ('#7c9a5a', .08)}
# [2차] 21 포장 광장, 22 수영장, 23 습지(갈대), 24 공원 잔디마당(밝은 잔디), 25 사석 호안, 26 계단식 호안, 27 부잔교 갑판, 28 숲 바닥(덤불)
AR = S['areas']
def areas(k):
    for a in AR.get(k, []):
        g = P(a['rings'])
        if g.intersects(GBOX): yield g, a
PARKN = ('여의도공원', '여의도한강공원', '여의도샛강생태공원')
for k, v in (('resi_land', 1), ('comm_land', 2), ('rail_land', 12), ('dirt', 11), ('grass', 3), ('wood', 28), ('wetland', 23)):
    for g, a in areas(k): fillg(g, 24 if (k == 'grass' and a['name'] in PARKN) else v)
GKM = None   # [테헤란로] 지면 종류 래스터(S['ground_raster'], teheran/ground_kinds.py): OSM 에 없는 땅(바탕 지면 0·1·2)의 종류. 뒤에 그리는 물·광장·주차장·도로가 덮는다
if S.get('ground_raster'):
    _gr = S['ground_raster']; _ki = Image.open(os.path.join(os.path.dirname(os.environ.get('P3D_SCENE', AREA + '/scene.json')), _gr['png'])); _g = _gr['g']
    _box = ((gx0 - _gr['x0']) / _g, (_gr['y1'] - gy1) / _g, (gx1 - _gr['x0']) / _g, (_gr['y1'] - gy0) / _g); _ka = np.asarray(_ki); _cl = np.array(CLS); _base = _cl <= 2; GKM = np.zeros(_cl.shape, np.uint8); _best = np.full(_cl.shape, 127, np.uint8)
    for _k, _v in sorted(_gr['map'].items()):   # 종류마다 부드럽게 키워(2 m 칸의 계단을 없앤다) 가장 센 종류를 고른다
        _m = np.asarray(Image.fromarray(((_ka == int(_k)) * 255).astype(np.uint8)).resize((GWp, GHp), Image.BILINEAR, box=_box)); _t = (_m > _best) & _base; GKM[_t] = int(_k); _cl[_t] = _v; _best[_t] = _m[_t]
    CLS = Image.fromarray(_cl); CD = ImageDraw.Draw(CLS)
WATER = unary_union([P(w['rings']) for w in S['water']]).buffer(0); WATERc = WATER.intersection(GBOX.buffer(5))
fillg(WATERc, 5)
for g, _ in areas('pond'): fillg(g, 6)
PLAZA = unary_union([g for g, _ in areas('plaza')] + [Point(0, 0).buffer(.01)])
for k, v in (('plaza', 21), ('pitch', 8), ('play', 9), ('parking', 10), ('pier', 18), ('pool', 22)):
    for g, _ in areas(k): fillg(g, 27 if (k == 'pier' and WATER.contains(g.representative_point())) else v)
# [2차] 호안: 물 쪽 5.5 m 띠(지면 메시에서 경사면/계단이 된다). 보행 광장에 닿은 곳은 계단식
REV = 5.5; RBAND = WATERc.difference(WATERc.buffer(-REV)); STEPZ = RBAND.intersection(PLAZA.buffer(8.0))
fillg(RBAND, 25); fillg(STEPZ, 26)
for st in S['streams']:
    ln = LineString(st['pts']).difference(WATERc.buffer(-1.0))  # 한강 수면 안으로 이어진 중심선은 그리지 않는다
    for q in ([ln] if ln.geom_type == 'LineString' else [x for x in getattr(ln, 'geoms', []) if x.geom_type == 'LineString']):
        if q.length > 1 and q.intersects(GBOX): lineg(q, st['w'] + 2.4, 19); lineg(q, st['w'], 6)
RD = [r for r in S['roads'] if not r['bridge'] and not r['tunnel'] and LineString(r['pts']).intersects(GBOX.buffer(30))]
for r in RD:
    if r['cls'] in ('foot', 'cycle'): lineg(LineString(r['pts']), max(r['w'], 1.2), 16 if r['cls'] == 'foot' else 17)
for r in RD:
    if r['cls'] == 'major' and r['hw'] in ('primary', 'secondary', 'tertiary', 'trunk'): lineg(LineString(r['pts']), r['w'] + 7.0, 13)
for r in RD:
    if r['cls'] == 'rail': lineg(LineString(r['pts']), 4.2, 12)
for r in RD:
    if r['cls'] == 'minor': lineg(LineString(r['pts']), r['w'], 15)
for r in RD:
    if r['cls'] == 'major': lineg(LineString(r['pts']), r['w'], 14)
# 팔레트 + 월드 고정 잡음(창이 달라도 같은 자리에 같은 무늬 → 이음매 없음)
cl = np.asarray(CLS); RGB = np.zeros((GHp, GWp, 3), np.uint8)
pal = np.array([np.array(ImageColor.getrgb(GC.get(i, ('#ff00ff', 0))[0]), float) for i in range(32)]); amp = np.array([GC.get(i, ('', 0))[1] for i in range(32)])
def hsh(ix, iy, s): v = (ix * 73856093) ^ (iy * 19349663) ^ (s * 83492791); v = (v ^ (v >> 13)) * 1274126177; return ((v ^ (v >> 16)) & 0xffff) / 65535.0
xs = gx0 + (np.arange(GWp) + .5) * GTEX
cr, sr = math.cos(math.radians(-32)), math.sin(math.radians(-32))  # 한강 흐름 방향(대략 서북서–동남동)
for j0 in range(0, GHp, 512):
    j1 = min(GHp, j0 + 512); ys = gy1 - (np.arange(j0, j1) + .5) * GTEX; WX_, WY_ = np.meshgrid(xs, ys)
    n = 0.6 * hsh(np.floor(WX_ / 0.5).astype(np.int64), np.floor(WY_ / 0.5).astype(np.int64), 1) + 0.4 * hsh(np.floor(WX_ / 2.3).astype(np.int64), np.floor(WY_ / 2.3).astype(np.int64), 2) - 0.5
    c_ = cl[j0:j1]; col = pal[c_] * (1 + 2 * amp[c_] * n)[..., None]
    wm = (c_ == 5)
    if wm.any():  # 물결: 흐름 방향으로 길쭉한 칸
        u_ = WX_ * cr + WY_ * sr; v_ = -WX_ * sr + WY_ * cr
        rp = hsh(np.floor(u_ / 7.0).astype(np.int64), np.floor(v_ / 0.9).astype(np.int64), 3)
        col[wm & (rp > 0.86)] = col[wm & (rp > 0.86)] * 1.13; col[wm & (rp < 0.08)] = col[wm & (rp < 0.08)] * 0.92
    RGB[j0:j1] = np.clip(col, 0, 255).astype(np.uint8)
GIMG = Image.fromarray(RGB); GD = ImageDraw.Draw(GIMG)
# 노면 표시(작업 해상도에서만)
def dashes(ln, on, off, w, col):
    L_ = ln.length; s = 0.0
    while s < L_:
        q = substring(ln, s, min(L_, s + on))
        if q.length > 0.05: GD.line(tp(q.coords), fill=col, width=max(1, int(round(w / GTEX))))
        s += on + off
def offs(ln, d):
    try: o = ln.offset_curve(d)
    except Exception: return []
    return [g for g in ([o] if o.geom_type == 'LineString' else getattr(o, 'geoms', [])) if not g.is_empty]
if FINE:
    for r in RD:
        ln = LineString(r['pts']).intersection(GBOX.buffer(10))
        if ln.is_empty or ln.geom_type not in ('LineString', 'MultiLineString'): continue
        for g in ([ln] if ln.geom_type == 'LineString' else list(ln.geoms)):
            if r['cls'] == 'major' and r['w'] >= 6:
                n_, w = r['lanes'], r['w']
                if r['oneway'] or n_ < 2:
                    for k in range(1, n_): [dashes(o, 3.0, 5.0, .15, '#eeeeea') for o in offs(g, -w / 2 + k * w / n_)]
                else:
                    for s_ in (-.18, .18): [GD.line(tp(o.coords), fill='#e2b13c', width=max(1, int(.15 / GTEX))) for o in offs(g, s_)]
                    for k in range(1, n_ // 2): [dashes(o, 3.0, 5.0, .15, '#eeeeea') for sg in (1, -1) for o in offs(g, sg * k * w / n_)]
                for sg in (1, -1): [GD.line(tp(o.coords), fill='#e8e8e2', width=max(1, int(.15 / GTEX))) for o in offs(g, sg * (w / 2 - .35))]
            elif r['cls'] == 'rail':
                for sg in (-.75, .75): [GD.line(tp(o.coords), fill='#4b4640', width=max(1, int(.12 / GTEX))) for o in offs(g, sg)]
                for s_ in np.arange(0, g.length, .65):
                    a_, b_ = g.interpolate(max(0, s_ - .05)), g.interpolate(min(g.length, s_ + .05)); dx, dy = b_.x - a_.x, b_.y - a_.y; L_ = math.hypot(dx, dy) or 1
                    nx, ny = -dy / L_, dx / L_; GD.line(tp([(a_.x - nx * 1.2, a_.y - ny * 1.2), (a_.x + nx * 1.2, a_.y + ny * 1.2)]), fill='#6e655a', width=max(1, int(.22 / GTEX)))
    for x, y, a, w in S['cross']:
        if not GBOX.contains(Point(x, y)): continue
        ca_, sa_ = math.cos(a), math.sin(a)
        for k in np.arange(-w / 2 + .4, w / 2 - .3, 1.0):
            c0 = (x - sa_ * k, y + ca_ * k); pts = [(c0[0] + ca_ * dx_ - (-sa_) * 0 + (-sa_) * dy_, c0[1] + sa_ * dx_ + ca_ * dy_) for dx_, dy_ in ((-1.5, 0), (1.5, 0), (1.5, .5), (-1.5, .5))]
            GD.polygon(tp(pts), fill='#ecebe6')
    for g, a in areas('parking'):
        mrr = g.minimum_rotated_rectangle; mc = np.array(mrr.exterior.coords); e0, e1 = mc[1] - mc[0], mc[2] - mc[1]
        ax_ = e0 if np.hypot(*e0) >= np.hypot(*e1) else e1; L_ = np.hypot(*ax_); ax_ = ax_ / L_; nm = np.array([-ax_[1], ax_[0]]); c_ = np.array(g.centroid.coords[0]); span = max(np.hypot(*e0), np.hypot(*e1))
        for s_ in np.arange(-span / 2, span / 2, 2.5):
            for side in (-1, 1):
                seg = LineString([c_ + ax_ * s_ + nm * side * 3.0, c_ + ax_ * s_ + nm * side * 8.0]).intersection(g)
                if seg.geom_type == 'LineString' and seg.length > .5: GD.line(tp(seg.coords), fill='#ecebe6', width=max(1, int(.12 / GTEX)))
    for ring_ in ([WATERc.exterior] if WATERc.geom_type == 'Polygon' else [p.exterior for p in parts(WATERc)]):
        pass
    for k_ in range(1, 5):  # 계단 단 끝선(물가선에서 1.375 m 간격 안쪽 오프셋)
        o_ = WATERc.buffer(-REV * k_ / 4).boundary.intersection(STEPZ.buffer(.3))
        for q in ([o_] if o_.geom_type == 'LineString' else [x for x in getattr(o_, 'geoms', []) if x.geom_type == 'LineString']):
            GD.line(tp(q.coords), fill='#9d988c', width=max(1, int(.16 / GTEX)))
    for g, a in areas('pool'):
        c_, ax_, Lx_, Ly_, _ = mrr_axes(g); nm_ = np.array([-ax_[1], ax_[0]])
        for p in parts(g.buffer(-.8)): GD.line(tp(p.exterior.coords), fill='#eef2f0', width=max(1, int(.5 / GTEX)))
        for k_ in np.arange(-Ly_ / 2 + 2.5, Ly_ / 2 - 2, 2.5):
            seg = LineString([c_ + nm_ * k_ - ax_ * Lx_, c_ + nm_ * k_ + ax_ * Lx_]).intersection(g.buffer(-2.5))
            if seg.geom_type == 'LineString' and seg.length > 1: GD.line(tp(seg.coords), fill='#2f7fb0', width=max(1, int(.2 / GTEX)))
    for g, a in areas('plaza'):  # 광장 바닥돌 줄눈(3 m 격자, 월드 고정)
        bx = g.bounds
        for xx in np.arange(math.floor(bx[0] / 3) * 3, bx[2], 3.0):
            seg = LineString([(xx, bx[1]), (xx, bx[3])]).intersection(g)
            for q in ([seg] if seg.geom_type == 'LineString' else [x for x in getattr(seg, 'geoms', []) if x.geom_type == 'LineString']): GD.line(tp(q.coords), fill='#c6bfb1', width=1)
        for yy in np.arange(math.floor(bx[1] / 3) * 3, bx[3], 3.0):
            seg = LineString([(bx[0], yy), (bx[2], yy)]).intersection(g)
            for q in ([seg] if seg.geom_type == 'LineString' else [x for x in getattr(seg, 'geoms', []) if x.geom_type == 'LineString']): GD.line(tp(q.coords), fill='#c6bfb1', width=1)
    for g, a in areas('pitch'):
        inn = g.buffer(-1.0)
        for p in parts(inn): GD.line(tp(p.exterior.coords), fill='#f0f0ea', width=max(1, int(.12 / GTEX)))
GPATH = f'{TEXD}/ground.png'; GIMG.save(GPATH)
print('ground', GWp, GHp, 'tex m', GTEX, 't', round(time.time() - T0, 1), flush=True)

# ---------- 띠창 입면(타워), 아파트 입면 ----------
def hexc(s, dflt):
    try: return '#%02x%02x%02x' % ImageColor.getrgb(s) if s else dflt
    except Exception: return dflt
def shade(hx, f): r, g, b = ImageColor.getrgb(hx); return '#%02x%02x%02x' % tuple(int(max(0, min(255, c * f))) for c in (r, g, b))
RPPM = 24
def ribbon_tex(key, glass, span, mull, flh=4.0, bay=1.6, spf=0.3, nb=8, nf=6, stripe=False):
    p = f'{TEXD}/rib_{key}.png'
    if os.path.exists(p): return p, nb * bay, nf * flh
    tw, th = int(nb * bay * RPPM), int(nf * flh * RPPM); im = Image.new('RGB', (tw, th), span); d = ImageDraw.Draw(im); rnd = random.Random(zlib.crc32(key.encode()))
    fp, bp = flh * RPPM, bay * RPPM
    for f in range(nf):
        y0_ = int(f * fp); ys_ = int(y0_ + fp * (1 - spf))
        for b_ in range(nb):
            x0_ = int(b_ * bp); g = glass if rnd.random() > .3 else shade(glass, rnd.choice([.86, 1.12, 1.2]))
            if stripe: g = shade(glass, .82 if b_ % 2 else 1.1)  # FKI: 비스듬한 태양광 패널이 만드는 세로 명암(추정)
            d.rectangle([x0_, y0_ + 2, x0_ + int(bp) - 1, ys_], fill=g)
            if rnd.random() < .35: d.polygon([(x0_, ys_), (x0_, y0_ + 2 + int(fp * .2)), (x0_ + int(bp * .6), y0_ + 2)], fill=shade(g, 1.12))
            d.line([(x0_, y0_), (x0_, y0_ + int(fp))], fill=mull, width=2)
        d.line([(0, y0_), (tw, y0_)], fill=shade(span, .8), width=2)
    im.save(p); return p, nb * bay, nf * flh
APTV = [('#efeee8', '#c9c7bd'), ('#ebe7dc', '#8aa0b4'), ('#efece4', '#c8b08a'), ('#e8e8e4', '#9a9890')]
def apt_tex(v):
    p = f'{TEXD}/apt_{v}.png'; wall, acc = APTV[v]
    if os.path.exists(p): return p, 10.8, 5.8
    tw, th = int(10.8 * 32), int(5.8 * 32); im = Image.new('RGB', (tw, th), wall); d = ImageDraw.Draw(im)
    for f in range(2):
        y0_ = f * th // 2; fh = th // 2
        for u in range(3):
            x0_ = u * tw // 3 + 6; x1_ = (u + 1) * tw // 3 - 6
            d.rectangle([x0_, y0_ + 8, x1_, y0_ + fh - 34], fill='#33475a')                      # 발코니 창
            d.rectangle([x0_ + 4, y0_ + 10, x0_ + (x1_ - x0_) // 3, y0_ + fh - 36], fill='#4d6880')
            for xx in range(x0_, x1_, 26): d.line([(xx, y0_ + 8), (xx, y0_ + fh - 34)], fill='#d9d9d2', width=2)
            d.rectangle([x0_ - 2, y0_ + fh - 34, x1_ + 2, y0_ + fh - 8], fill=wall)                  # 난간 벽
            d.line([(x0_ - 2, y0_ + fh - 34), (x1_ + 2, y0_ + fh - 34)], fill=shade(wall, .82), width=2)
            if f == 0 and u == 1: d.rectangle([x0_ + 10, y0_ + fh - 30, x0_ + 34, y0_ + fh - 14], fill='#e4e4de', outline='#9a9a94')  # 실외기
        d.rectangle([0, y0_ + fh - 6, tw, y0_ + fh], fill=shade(wall, .9))
        d.rectangle([tw // 3 - 6, y0_, tw // 3 + 6, y0_ + fh], fill=acc); d.rectangle([2 * tw // 3 - 6, y0_, 2 * tw // 3 + 6, y0_ + fh], fill=acc)
    im.save(p); return p, 10.8, 5.8
def skin(mb, poly, z0, ztop, m, tw, th, u0=0.0):
    """벽면: 변마다 사각형 하나, UV 는 미터 기준(평면이라 윗변이 기울어도 정확). ztop(x,y) → 윗변 높이."""
    s = u0
    for ring in [poly.exterior] + list(poly.interiors):
        c = list(ring.coords)
        for a, b in zip(c[:-1], c[1:]):
            L_ = math.hypot(b[0] - a[0], b[1] - a[1])
            if L_ < .05: continue
            za, zb = ztop(*a), ztop(*b)
            mb.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], zb), (a[0], a[1], za)], m, [(s / tw, z0 / th), ((s + L_) / tw, z0 / th), ((s + L_) / tw, zb / th), (s / tw, za / th)]); s += L_
def capf(mb, poly, ztop, m):
    for t in shapely.constrained_delaunay_triangles(poly).geoms: mb.face([(x, y, ztop(x, y)) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], m)
def mrr_axes(poly):
    mc = np.array(poly.minimum_rotated_rectangle.exterior.coords); e0, e1 = mc[1] - mc[0], mc[2] - mc[1]
    if np.hypot(*e0) < np.hypot(*e1): e0, e1 = e1, e0
    return np.array(poly.centroid.coords[0]), e0 / np.hypot(*e0), np.hypot(*e0), np.hypot(*e1), mc[:4]

# 랜드마크 건물별 설정(공개 자료의 높이·층수 + 외관 색·상부 형태. 색은 추정값, NOTES 참고)
LMC = {  # [2차] 근거는 NOTES §4. hroof/htop: 지붕·첨탑 높이(위키백과), lobby: 저층 로비 띠, belts: 기계층 띠(높이 비율), crown: 상부 형태
    'parc1': dict(glass='#7b8e9c', span='#5d6872', mull='#c8ced2', flh=4.4, bay=1.5, frame='#c43a2a', top='frame', hroof=318.0, htop=333.0, belts=(.33, .66)),
    'parc2': dict(glass='#7b8e9c', span='#5d6872', mull='#c8ced2', flh=4.4, bay=1.5, frame='#c43a2a', top='frame', hroof=242.0, htop=256.0, belts=(.4, .75)),
    'ifc1': dict(glass='#5f86bf', span='#48678f', mull='#b9c8dc', flh=4.2, top='slant', rise=18, sdir=(0.6, 0.8)),
    'ifc2': dict(glass='#5f86bf', span='#48678f', mull='#b9c8dc', flh=4.2, top='slant', rise=16, sdir=(-0.6, 0.8)),
    'ifc3': dict(glass='#547bbc', span='#3f5f8f', mull='#b9c8dc', flh=4.2, top='disc', hroof=279.0, htop=285.0),
    'conrad': dict(glass='#6a8fb8', span='#4f6d8f', mull='#c0ccdc', flh=4.0, top='slant', rise=14, sdir=(-0.8, -0.6)),
    'lg': dict(glass='#7a705f', span='#5b5244', mull='#b9ab8c', flh=3.8, bay=1.5, spf=.38, top='flat', heli=False, crownband=2.4),
    'fki': dict(glass='#86a2ae', span='#5d7680', mull='#d0dadd', flh=4.4, top='slant', rise=30, sdir=(-0.6, -0.8), stripe=True, hroof=245.5),
    'anchor': dict(glass='#6f8291', span='#55626d', mull='#cfd5d8', flh=4.2, top='step'),
    'post': dict(glass='#8696a2', span='#d8d6ce', mull='#e0e0dc', flh=4.0, top='step'),
}
TOWERG = [('#6d8aa6', '#4f6278', '#c3ccd4'), ('#5d8a8c', '#476a6c', '#c6d4d2'), ('#8b97a0', '#6a737a', '#d8dcde'), ('#7d8c78', '#5d6a5a', '#d0d6cc'), ('#9a8f7c', '#7a705e', '#ddd6c8'), ('#56708e', '#3d4f66', '#b8c4d0')]
def tower(b, idx, cfg=None):
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = (cfg or {}).get('hroof') or b['h']; rnd = random.Random(b['seed']); mb = MB(); gen_ = cfg is None; up_ = None
    if cfg is None:
        g, s_, m_ = rnd.choice(TOWERG); col = hexc(b.get('colour'), '')
        if col:  # OSM building:colour 는 원색이 많다 → 회색과 30% 섞음(추정 보정)
            r1, g1, b1 = ImageColor.getrgb(col); col = '#%02x%02x%02x' % tuple(int(v * .7 + w * .3) for v, w in zip((r1, g1, b1), (138, 144, 150))); g, s_ = col, shade(col, .78)
        cfg = dict(glass=g, span=s_, mull=m_, flh=4.0, top=rnd.choice(['flat', 'flat', 'step']) if h > 60 else 'flat')
    path, tw, th = ribbon_tex(f"{cfg['glass']}_{cfg['span']}_{cfg['flh']}_{cfg.get('bay', 1.6)}_{cfg.get('stripe', False)}", cfg['glass'], cfg['span'], cfg['mull'], cfg['flh'], cfg.get('bay', 1.6), cfg.get('spf', .3), stripe=cfg.get('stripe', False))
    gm = mat_tex(path, 'rib_' + path); c, ax_, Lx, Ly, mc = mrr_axes(poly)
    top = cfg.get('top', 'flat'); ztop = lambda x, y: h
    if top == 'slant':
        dv = np.array(cfg['sdir'], float); dv /= np.hypot(*dv); pr = np.array(poly.exterior.coords) @ dv; lo, hi = pr.min(), pr.max(); rise = cfg['rise']
        ztop = lambda x, y: h - rise + rise * ((x * dv[0] + y * dv[1]) - lo) / max(hi - lo, 1e-6)
    LB = 8.0 if h >= 60 else 0.0  # [2차] 저층 로비 띠(높은 유리·짙은 색)
    if LB:
        lp, ltw, lth = ribbon_tex(f"lobby_{cfg['span']}", shade(cfg['glass'], .55), shade(cfg['span'], .7), cfg['mull'], LB, 3.0, .04, nf=1)
        skin(mb, poly, 0.0, lambda x, y: LB, mat_tex(lp, 'rib_' + lp), ltw, lth)
        cn = orient(poly.buffer(1.6, join_style=2), 1.0)  # 로비 위 차양 띠
        skin(mb, cn, LB, lambda x, y: LB + .6, mat_flat(shade(cfg['span'], 1.2)), 1, 1); capf(mb, cn, lambda x, y: LB + .6, mat_flat(shade(cfg['span'], 1.1)))
    skin(mb, poly, LB, ztop, gm, tw, th)
    for fr in cfg.get('belts', ()):  # 기계층 띠(루버)
        zb_ = h * fr; bp_ = orient(poly.buffer(.25, join_style=2), 1.0); skin(mb, bp_, zb_, lambda x, y: zb_ + 4.4, mat_flat(shade(cfg['span'], .8)), 1, 1)
    roofm = mat_flat('#8f9296')
    if top == 'slant': capf(mb, poly, lambda x, y: ztop(x, y), mat_flat(shade(cfg['glass'], 1.1)))
    else:
        capf(mb, poly, ztop, roofm); inner = poly.buffer(-0.5, join_style=2)
        if inner.geom_type == 'Polygon' and inner.area > 10:  # 파라펫
            for ring, fl in ((poly.exterior, False), (inner.exterior, True)):
                cc = list(ring.coords)
                for a_, q in zip(cc[:-1], cc[1:]):
                    pts = [(a_[0], a_[1], h), (q[0], q[1], h), (q[0], q[1], h + 1.4), (a_[0], a_[1], h + 1.4)]; mb.face(pts[::-1] if fl else pts, mat_flat(cfg['span']))
            for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms: mb.face([(x, y, h + 1.4) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat(shade(cfg['span'], 1.15)))
        if cfg.get('crownband'):  # 꼭대기 테 띠
            cb = orient(poly.buffer(.3, join_style=2), 1.0); skin(mb, cb, h - cfg['crownband'], lambda x, y: h + 1.4, mat_flat(shade(cfg['span'], 1.25)), 1, 1)
        if top == 'disc':  # 3 IFC: 지붕 위 원판 크라운(헬리포트, 사진) + 짧은 기둥
            ht_ = cfg.get('htop', h + 6); mb.cyl((c[0], c[1], h), .2 * Ly, ht_ - h - 1.6, mat_flat(shade(cfg['span'], 1.1)), n=16)
            mb.cyl((c[0], c[1], ht_ - 1.6), .48 * Ly, 1.6, mat_flat('#c9ced3'), mat_flat('#5a5d61'), n=32); mb.cyl((c[0], c[1], ht_), .3 * Ly, .04, mat_flat('#e2c33c'), mat_flat('#5a5d61'), n=24)
        if top == 'step':  # 상부 기계실·크라운(한 단 들어간 상자)
            cr_ = poly.buffer(-min(4.0, 0.18 * Ly), join_style=2)
            if cr_.geom_type == 'Polygon' and cr_.area > 30:
                hz = min(9.0, 0.05 * h + 3); skin(mb, cr_, h, lambda x, y: h + hz, gm, tw, th); capf(mb, cr_, lambda x, y: h + hz, roofm); h2 = h + hz; up_ = (cr_, h2)
            else: h2 = h
        else: h2 = h
        core = poly.buffer(-max(2.5, 0.28 * Ly), join_style=2)
        if top in ('flat',) and core.geom_type == 'Polygon' and core.area > 15:
            skin(mb, core, h, lambda x, y: h + 4.5, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: h + 4.5, mat_flat('#8c8e90')); up_ = (core, h + 4.5)
        if h >= 100 and top not in ('frame', 'disc') and cfg.get('heli', True):  # 헬리패드 [랜드마크 2차] 위성뷰: 네모 판 + 흰 테두리 + 원(lm_build.py heli_std), 높이 100 m 이상
            heli_std(mb, c, ax_, h2 + (4.5 if (top == 'flat' and core.geom_type == 'Polygon' and core.area > 15) else 0), Ly, rnd)
        if top == 'frame' and core.geom_type == 'Polygon' and core.area > 15:   # [2차] 파크원 옥상 기계실·설비(배치·크기 추정)
            skin(mb, core, h, lambda x, y: h + 6.0, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: h + 6.0, mat_flat('#8c8e90'))
        if top in ('frame', 'flat') and h >= 60: roof_kit(mb, poly, h, rnd, 3 + int(poly.area // 900))   # 냉각탑·물탱크·기계실(추정)
        if gen_: roof_std(mb, poly, h, up_[0] if up_ else None, up_[1] if up_ else h, h >= 100, b['seed'])   # [랜드마크 4차] 지붕 잠금용 옥상: 바닥 색 구획·턱·설비(lm_build.py)
    if top == 'frame':  # 파크원: 붉은 외부 기둥(모서리) + 층 띠 보 + 지붕 위로 솟은 프레임
        fm = mat_flat(cfg['frame']); q = Polygon(mc).buffer(1.2, join_style=2); qc = list(orient(q, 1.0).exterior.coords)[:-1]
        qc = qc if len(qc) == 4 else list(np.array(mc))
        ht = cfg.get('htop', h + 22)
        for k in range(4):  # [2차] 모서리 양쪽 면에 붉은 거대 기둥 한 쌍(사진), 꼭대기에서 보로 묶여 지붕 위로 솟은 열린 프레임
            a_, b_ = np.array(qc[k]), np.array(qc[(k + 1) % 4]); e = b_ - a_; L_ = np.hypot(*e); ang = math.atan2(e[1], e[0]); ed = e / L_
            for p_ in (a_ + ed * 3.2, b_ - ed * 3.2): mb.box((p_[0], p_[1], 0), 1.3, 1.1, ht + .35, fm, ang)
            for zb in (h + .2, ht - 2.2): mb.box(((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2, zb), L_ / 2 - 2.0, .6, 2.2, fm, ang)
    mb.build('b%d' % idx, idx)

def apartment(b, idx):
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = b['h']; rnd = random.Random(b['seed']); mb = MB(); v = rnd.randrange(len(APTV))
    path, tw, th = apt_tex(v); am = mat_tex(path, 'apt_%d' % v); endm = mat_flat(shade(APTV[v][0], .96))
    s = 0.0
    for ring in [poly.exterior] + list(poly.interiors):
        for seq in ring_runs(list(ring.coords)):  # 곡면 구간 단위: 휜 아파트 동도 발코니 입면이 이어진다
            ar = _arc(seq); m = am if ar[-1] >= 5 else endm
            for k in range(len(seq) - 1):
                a, q = seq[k], seq[k + 1]; u0, u1 = (s + ar[k]) / tw, (s + ar[k + 1]) / tw
                if ar[k + 1] - ar[k] < 1e-4: continue
                mb.face([(a[0], a[1], 0), (q[0], q[1], 0), (q[0], q[1], h), (a[0], a[1], h)], m, [(u0, 0), (u1, 0), (u1, h / th), (u0, h / th)])
            s += ar[-1]
    capf(mb, poly, lambda x, y: h, mat_flat(rnd.choice(['#63ad8c', '#5ba684', '#6bb394', '#63ad8c', '#9d9c96']) if h <= 50 else '#9d9c96'))   # [랜드마크 3차 위성뷰] 여의도의 오래된 판상형 아파트(15층 안팎) 옥상은 거의 다 민트빛 초록 방수 바닥
    inner = poly.buffer(-0.35, join_style=2)
    if inner.geom_type == 'Polygon' and inner.area > 8:
        for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms: mb.face([(x, y, h + .9) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat(APTV[v][0]))
        for ring, fl in ((poly.exterior, False), (inner.exterior, True)):
            cc = list(ring.coords)
            for a_, q in zip(cc[:-1], cc[1:]):
                pts = [(a_[0], a_[1], h), (q[0], q[1], h), (q[0], q[1], h + .9), (a_[0], a_[1], h + .9)]; mb.face(pts[::-1] if fl else pts, mat_flat(APTV[v][0]))
    c, ax_, Lx, Ly, _ = mrr_axes(poly); ang = math.atan2(ax_[1], ax_[0])
    for k in range(max(1, int(Lx // 22))):  # 승강기 옥탑
        t_ = (k + .5) / max(1, int(Lx // 22)) - .5; p_ = c + ax_ * t_ * Lx * .8
        if poly.buffer(-1.5).contains(Point(*p_)): mb.box((p_[0], p_[1], h), 2.2, min(2.0, Ly * .3), 3.2, mat_flat(APTV[v][0]), ang, mat_flat('#8f8e88'))
    if rnd.random() < .5 and poly.buffer(-2).contains(Point(*c)): mb.cyl((c[0], c[1], h), .9, 1.4, mat_flat('#3f86c9'), mat_flat('#e8e6dc'))
    mb.build('b%d' % idx, idx)

def b63(lm, idx):
    """63빌딩 전용. 근거: OSM 파트(바닥 짧은 축 ≈43 m, 120 m 날개, 249 m 핵심부 ≈27 m, 짧은 변 가운데 폭 ≈4 m 오목부) + 공개 사진에서 읽은 것:
    짧은 끝면의 세로 윤곽이 아래로 갈수록 바깥으로 퍼지는 오목 곡선(위는 거의 곧음), 넓은 면 모서리는 곧은 수직선, 끝면 가운데 전체 높이 세로 홈,
    금색 유리가 꼭대기까지, 맨 위에 어두운 전망층 띠와 안테나. 고리는 반 층(1.95 m)마다 + 부드러운 음영."""
    poly = unary_union([P(r) for r in lm['rings']]); c, ax_, Lx, Ly, _ = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]])
    H = 249.0; hu0, hv0, hvt = Lx / 2, Ly / 2, 13.3; mb = MB()
    path, tw, th = ribbon_tex('gold63', '#c9a24c', '#a9833a', '#7d5f26', flh=3.9, bay=1.5, spf=0.18)
    gm = mat_tex(path, 'gold63'); dk = mat_flat('#3a3226'); GW, GD = 2.1, 1.4; NA = 2
    def loc_ring(hu, hv):
        rc = 0.9; pts = []
        def arc(cx, cy, a0):
            for k in range(NA + 1): a = math.radians(a0 + 90 * k / NA); pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
        pts += [(hu, -GW), (hu - GD, -GW), (hu - GD, GW), (hu, GW)]; arc(hu - rc, hv - rc, 0); arc(-hu + rc, hv - rc, 90)
        pts += [(-hu, GW), (-hu + GD, GW), (-hu + GD, -GW), (-hu, -GW)]; arc(-hu + rc, -hv + rc, 180); arc(hu - rc, -hv + rc, 270)
        return pts
    def prof(z):  # 짧은 축 반폭: 오목(아래가 퍼짐) — (1-t)^2.2
        t = min(1.0, z / H); return hu0, hvt + (hv0 - hvt) * (1 - t) ** 2.2
    zs = sorted(set([round(z, 3) for z in np.arange(0, H, 1.95)] + [H - 4.2, H]))
    R_ = [[tuple(c + ax_ * u + nv * v) + (z,) for u, v in loc_ring(*prof(z))] for z in zs]; n = len(R_[0])
    seg = lambda Rg, i: math.hypot(Rg[(i + 1) % n][0] - Rg[i][0], Rg[(i + 1) % n][1] - Rg[i][1])
    L0 = [seg(R_[0], i) for i in range(n)]; uc = np.cumsum([0] + L0)[:-1] + np.array(L0) / 2
    for k in range(len(zs) - 1):
        A_, B_ = R_[k], R_[k + 1]; m = dk if zs[k] >= H - 4.25 else gm  # 맨 위 전망층 띠
        for i in range(n):
            a, b_, c2, d2 = A_[i], A_[(i + 1) % n], B_[(i + 1) % n], B_[i]; La, Lb = seg(A_, i), seg(B_, i)
            if La < 1e-4 and Lb < 1e-4: continue
            mb.face([a, b_, c2, d2], m, [((uc[i] - La / 2) / tw, a[2] / th), ((uc[i] + La / 2) / tw, a[2] / th), ((uc[i] + Lb / 2) / tw, c2[2] / th), ((uc[i] - Lb / 2) / tw, d2[2] / th)])
    top = Polygon([p[:2] for p in R_[-1]]).buffer(0); capf(mb, top, lambda x, y: H, mat_flat('#9c9a94'))
    cr_ = top.buffer(-0.6, join_style=2)
    for ring_, fl in ((top.exterior, False), (cr_.exterior, True)):  # 얇은 밝은 테두리
        cc = list(ring_.coords)
        for a_, q in zip(cc[:-1], cc[1:]):
            pts = [(a_[0], a_[1], H), (q[0], q[1], H), (q[0], q[1], H + 1.2), (a_[0], a_[1], H + 1.2)]; mb.face(pts[::-1] if fl else pts, mat_flat('#d9d4c4'))
    for t in shapely.constrained_delaunay_triangles(top.difference(cr_)).geoms: mb.face([(x, y, H + 1.2) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat('#e2ddcc'))
    mb.box((c[0], c[1], H), 7.0, 4.0, 4.5, mat_flat('#8f8c84'), math.atan2(ax_[1], ax_[0]), mat_flat('#7c7a74'))  # 옥상 기계실
    for k in range(5):  # 안테나(빨강·흰 띠)
        mb.cyl((c[0], c[1], H + 4.5 + k * 3.0), .45 - k * .05, 3.0, mat_flat('#c8402e' if k % 2 == 0 else '#efefea'), n=8)
    mb.build('b63', idx)

# ================= [2차] 랜드마크·시설 빌더 =================
def beam(mb, p0, p1, w, m, hgt=None):
    """임의 방향 각기둥(단면 w×hgt). 교량 아치·철탑 다리·트러스 부재."""
    p0, p1 = np.array(p0, float), np.array(p1, float); d = p1 - p0; L_ = np.linalg.norm(d)
    if L_ < 1e-4: return
    d /= L_; up = np.array([0, 0, 1.0]) if abs(d[2]) < .95 else np.array([1.0, 0, 0])
    a = np.cross(d, up); a /= np.linalg.norm(a); b = np.cross(a, d); hw, hh = w / 2, (hgt or w) / 2
    q = [a * hw + b * hh, -a * hw + b * hh, -a * hw - b * hh, a * hw - b * hh]
    for k in range(4):
        u0, u1 = q[k], q[(k + 1) % 4]; mb.face([tuple(p0 + u0), tuple(p0 + u1), tuple(p1 + u1), tuple(p1 + u0)], m)
    mb.face([tuple(p1 + u) for u in q[::-1]], m); mb.face([tuple(p0 + u) for u in q], m)
def obox(mb, c, ax, sx, sy, z0, z1, m, top=None):
    """축 ax(단위벡터) 기준 회전 상자: 반폭 sx(ax 방향)·sy, z0..z1."""
    mb.box((c[0], c[1], z0), sx, sy, z1 - z0, m, math.atan2(ax[1], ax[0]), top)
def taper(mb, c, ax, sx0, sy0, sx1, sy1, z0, z1, m):
    """아래(sx0,sy0)→위(sx1,sy1)로 폭이 변하는 각기둥(교각 머리 등)."""
    nv = np.array([-ax[1], ax[0]]); cc = np.array(c[:2], float)
    q0 = [cc + ax * u * sx0 + nv * v * sy0 for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    q1 = [cc + ax * u * sx1 + nv * v * sy1 for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for k in range(4):
        a, b = k, (k + 1) % 4; mb.face([(*q0[a], z0), (*q0[b], z0), (*q1[b], z1), (*q1[a], z1)], m)
    mb.face([(*p, z1) for p in q1], m)
def finwall_tex(key, wall, win, fin, bay=2.4, flh=4.0, finw=.35):
    """돌 외장 + 세로 핀(기둥선) + 움푹한 창. 국회 부속 건물·KBS·거래소."""
    p = f'{TEXD}/fin_{key}.png'
    if os.path.exists(p): return p, bay * 4, flh * 2
    tw, th = int(bay * 4 * RPPM), int(flh * 2 * RPPM); im = Image.new('RGB', (tw, th), wall); d = ImageDraw.Draw(im); bp, fp = bay * RPPM, flh * RPPM
    for f in range(2):
        for b_ in range(4):
            x0_, y0_ = int(b_ * bp), int(f * fp); d.rectangle([x0_ + int(finw * RPPM), y0_ + int(.9 * RPPM), x0_ + int(bp) - 1, y0_ + int(fp * .78)], fill=win)
            d.line([(x0_ + int(finw * RPPM), y0_ + int(fp * .5)), (x0_ + int(bp), y0_ + int(fp * .5))], fill=shade(win, 1.25), width=1)
            d.rectangle([x0_, y0_, x0_ + int(finw * RPPM), y0_ + int(fp)], fill=fin)
        d.line([(0, int(f * fp)), (tw, int(f * fp))], fill=shade(wall, .86), width=2)
    im.save(p); return p, bay * 4, flh * 2
def flat_roof(mb, poly, h, wallhex, roofhex='#a3a29b', par=.9):
    capf(mb, poly, lambda x, y: h, mat_flat(roofhex)); inner = poly.buffer(-.4, join_style=2)
    if inner.geom_type == 'Polygon' and inner.area > 8:
        for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms: mb.face([(x, y, h + par) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat(shade(wallhex, 1.05)))
        for ring, fl in ((poly.exterior, False), (inner.exterior, True)):
            cc = list(ring.coords)
            for a_, q in zip(cc[:-1], cc[1:]): pts = [(a_[0], a_[1], h), (q[0], q[1], h), (q[0], q[1], h + par), (a_[0], a_[1], h + par)]; mb.face(pts[::-1] if fl else pts, mat_flat(wallhex))
def roof_kit(mb, poly, h, rnd, n=3):
    area = poly.buffer(-3.0)
    if area.is_empty: return
    x0, y0, x1, y1 = area.bounds; c_, ax_, Lx_, Ly_, _ = mrr_axes(poly); ang = math.atan2(ax_[1], ax_[0])
    for _ in range(n):
        for _t in range(20):
            p_ = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
            if area.contains(p_): break
        else: continue
        k_ = rnd.random()
        if k_ < .45: mb.box((p_.x, p_.y, h), rnd.uniform(2, 4), rnd.uniform(1.5, 3), rnd.uniform(1.8, 3.2), mat_flat('#9a9b97'), ang, mat_flat('#85878a'))   # 기계실
        elif k_ < .8:
            for j in range(3): mb.box((p_.x + (j - 1) * 2.4 * math.cos(ang), p_.y + (j - 1) * 2.4 * math.sin(ang), h), 1.0, 1.0, 1.4, mat_flat('#c9cbc8'), ang, mat_flat('#6d7073'))  # 냉각탑(팬)
        else: mb.cyl((p_.x, p_.y, h), 1.3, 2.2, mat_flat('#d8d8d2'), mat_flat('#b5b5ae'), n=10)  # 물탱크
def finwall_bld(b, idx, wall='#d8d2c4', win='#3f4a55', fin='#ece8de', bay=2.4, flh=4.0, extra=None):
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = b['h']; mb = MB(); path, tw, th = finwall_tex(f'{wall}{win}{fin}{bay}', wall, win, fin, bay, flh)
    skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'fin_' + path), tw, th); flat_roof(mb, poly, h, fin); roof_kit(mb, poly, h, random.Random(b['seed']), 2 + int(poly.area // 1500))
    if extra: extra(mb, poly, h)
    mb.build('b%d' % idx, idx)
def lattice_tower(mb, c, z0, H, base, top, mr='#c8402e', mw='#eeeeea', nseg=8):
    """KBS 옥상 송신 철탑: 네 다리가 위로 모이는 격자탑(빨강·흰 띠)."""
    for k in range(nseg):
        za, zb = z0 + H * k / nseg, z0 + H * (k + 1) / nseg; ra, rb = base + (top - base) * k / nseg, base + (top - base) * (k + 1) / nseg; m = mat_flat(mr if k % 2 == 0 else mw)
        cs = [(c[0] + sx * ra, c[1] + sy * ra) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]; ct = [(c[0] + sx * rb, c[1] + sy * rb) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for j in range(4):
            beam(mb, (*cs[j], za), (*ct[j], zb), .45, m)
            beam(mb, (*cs[j], za), (*ct[(j + 1) % 4], zb), .18, m); beam(mb, (*ct[j], zb), (*ct[(j + 1) % 4], zb), .2, m)
    mb.cyl((c[0], c[1], z0 + H), .25, H * .18, mat_flat(mr), n=6)
def pavilion(b, idx, kind='jeong'):
    """정자(공원 OSM building=roof/hut) 또는 그늘막. 정자: 붉은 기둥 + 짙은 기와 모임지붕(추정)."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 4: return
    c_, ax_, Lx, Ly, mc = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); mb = MB()
    if kind == 'jeong':
        mb.face([(x, y, .6) for x, y in list(orient(Polygon(mc), 1.0).exterior.coords)[:-1]], mat_flat('#a8957a'))
        skin(mb, Polygon(mc), 0.0, lambda x, y: .6, mat_flat('#bdb3a0'), 1, 1)
        for su in (-1, 1):
            for sv in (-1, 1): p_ = c_ + ax_ * su * (Lx / 2 - .4) + nv * sv * (Ly / 2 - .4); mb.cyl((p_[0], p_[1], .6), .18, 2.7, mat_flat('#8a3a2a'), n=8)
        e = [c_ + ax_ * su * (Lx / 2 + 1.1) + nv * sv * (Ly / 2 + 1.1) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]; z_e, z_r = 3.2, 3.2 + .45 * min(Lx, Ly) + 1.0
        rd = ax_ * max(0.0, (Lx - Ly) / 2); r0, r1 = c_ - rd, c_ + rd; rm = mat_flat('#4d5258')
        mb.face([(*e[0], z_e), (*e[1], z_e), (*r1, z_r), (*r0, z_r)], rm); mb.face([(*e[2], z_e), (*e[3], z_e), (*r0, z_r), (*r1, z_r)], rm)
        mb.face([(*e[1], z_e), (*e[2], z_e), (*r1, z_r)], rm); mb.face([(*e[3], z_e), (*e[0], z_e), (*r0, z_r)], rm)
        mb.face([(*e[3], z_e), (*e[2], z_e), (*e[1], z_e), (*e[0], z_e)], mat_flat('#6a4a36'))
    else:  # 그늘막: 기둥 4 + 얇은 판
        for su in (-1, 1):
            for sv in (-1, 1): p_ = c_ + ax_ * su * (Lx / 2 - .3) + nv * sv * (Ly / 2 - .3); mb.cyl((p_[0], p_[1], 0), .1, 3.0, mat_flat('#8d9094'), n=6)
        obox(mb, c_, ax_, Lx / 2, Ly / 2, 3.0, 3.25, mat_flat('#e6e3da'))
    mb.build('b%d' % idx, idx)
def church(b, idx):
    """여의도순복음교회 대성전(추정): 둥근 평면의 흰 벽 + 세로 띠창, 낮은 돔 지붕, 큰길 쪽 십자가 탑(사진 1장: 탑 위 십자가, 둥근 본당)."""
    poly = orient(P(b['rings']), 1.0); h = max(b['h'], 22.0); mb = MB()
    path, tw, th = finwall_tex('church', '#ece6d8', '#6c7f97', '#f4efe4', bay=3.2, flh=5.5, finw=1.4)
    skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'fin_' + path), tw, th)
    c_, ax_, Lx, Ly, _ = mrr_axes(poly); cen = np.array(poly.centroid.coords[0]); R = math.sqrt(poly.area / math.pi)
    capf(mb, poly, lambda x, y: h, mat_flat('#4c9672'))   # [랜드마크 2차 위성뷰] 돔 둘레 낮은 지붕은 초록 방수 바닥
    rr = [R * .92 * math.cos(math.radians(a_)) for a_ in range(0, 91, 15)]; zz = [h + 7.5 * math.sin(math.radians(a_)) for a_ in range(0, 91, 15)]
    prev = None; dm = mat_flat('#b9c7b6')   # [랜드마크 2차 위성뷰] 돔은 옅은 회녹색
    for r_, z_ in zip(rr, zz):
        ring = [(cen[0] + r_ * math.cos(2 * math.pi * k / 32), cen[1] + r_ * math.sin(2 * math.pi * k / 32), z_) for k in range(32)]
        if prev:
            for k in range(32): mb.face([prev[k], prev[(k + 1) % 32], ring[(k + 1) % 32], ring[k]], dm)
        prev = ring
    rd_ = [LineString(r['pts']) for r in RD if r['cls'] == 'major']
    if rd_:
        near = min(rd_, key=lambda l: l.distance(Point(*cen))); q = near.interpolate(near.project(Point(*cen))); dv = np.array([q.x, q.y]) - cen; dv /= (np.hypot(*dv) or 1)
        bp = poly.exterior.interpolate(poly.exterior.project(Point(*(cen + dv * R * 2)))); tc = np.array([bp.x, bp.y]) + dv * 1.0; ax2 = np.array([-dv[1], dv[0]])
        obox(mb, tc, ax2, 5.0, 3.0, 0.0, h + 16, mat_flat('#f2efe8'), mat_flat('#d8d4ca'))
        obox(mb, tc, ax2, .5, .5, h + 16, h + 26, mat_flat('#d23a2e')); obox(mb, (tc[0], tc[1]), ax2, 2.6, .5, h + 21.5, h + 22.6, mat_flat('#d23a2e'))
    mb.build('b%d' % idx, idx)
def hyundai(b, idx):
    """더현대 서울(추정 포함): 가로 루버 띠 외장 + 긴 축을 따라 볼록한 유리 천창(내부 사진의 자연채광 천장) + 옥상 녹지 조각."""
    poly = orient(P(b['rings']), 1.0); h = max(b['h'], 30.0); mb = MB()
    path, tw, th = ribbon_tex('hyundai', '#8fa2ad', '#cfc7b8', '#e3ddd0', flh=5.0, bay=3.0, spf=.55)
    skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'rib_' + path), tw, th); flat_roof(mb, poly, h, '#d8d1c2')
    c_, ax_, Lx, Ly, _ = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); gm = mat_flat('#9fc3d6'); rib = mat_flat('#e6e4de')
    sw = .22 * Ly; L2 = .38 * Lx; N = 8
    prof_ = [(sw * math.cos(math.pi * k / N), 3.5 * math.sin(math.pi * k / N)) for k in range(N + 1)]
    for k in range(N):
        (v0, z0), (v1, z1) = prof_[k], prof_[k + 1]
        a0, a1 = c_ - ax_ * L2, c_ + ax_ * L2
        mb.face([(*(a0 + nv * v0), h + z0), (*(a1 + nv * v0), h + z0), (*(a1 + nv * v1), h + z1), (*(a0 + nv * v1), h + z1)], gm)
    for s_ in np.linspace(-L2, L2, 12):
        for k in range(N): (v0, z0), (v1, z1) = prof_[k], prof_[k + 1]; p0 = c_ + ax_ * s_; beam(mb, (*(p0 + nv * v0), h + z0 + .05), (*(p0 + nv * v1), h + z1 + .05), .25, rib)
    for sv in (-1, 1):
        q0 = c_ + nv * sv * (sw + 6.5); obox(mb, q0, ax_, L2 * .8, 3.5, h, h + .5, mat_flat('#6f9e52'))   # 옥상 녹지(추정)
    roof_kit(mb, poly.buffer(-.0), h, random.Random(7), 3)
    mb.build('b%d' % idx, idx)
def glass_pav(b, idx):
    poly = orient(P(b['rings']), 1.0); h = max(5.0, min(b['h'], 9.0)); mb = MB()
    path, tw, th = ribbon_tex('pav', '#8fb2c8', '#5e7180', '#dfe5ea', flh=h, bay=1.5, spf=.05, nf=1)
    skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'rib_' + path), tw, th); capf(mb, poly, lambda x, y: h, mat_flat('#a9c4d4')); mb.build('b%d' % idx, idx)

def assembly(lm, idx):
    """국회의사당 본관(전용). 근거: 국가기록원·위키백과 — 길이 122 m·폭 81 m, 기둥 24개(앞·뒤 8, 양옆 4 = 모서리 포함 측면 6), 팔각 화강암 기둥,
    돔 밑지름 64 m·동판(청록), 사진 3장 — 정면은 남동(앞 잔디광장·분수 쪽), 기둥 바깥 열주 + 두꺼운 평판 처마, 돔은 흰 받침 위 낮은 반구, 정면 가운데 짙은 갈색 격자.
    추정: 높이(처마 36.5 m, 돔 꼭대기 ≈57 m — 정면 사진 비례), 돔 높이, 기단 1.4 m 와 계단 형태, 본체 들여쌓기 7 m."""
    poly = unary_union([P(r) for r in lm['rings']]); cen = np.array(poly.centroid.coords[0]); a = math.radians(38.0)
    ax_ = np.array([math.cos(a), math.sin(a)]); nv = np.array([-math.sin(a), math.cos(a)])  # nv = 북서(뒤), -nv = 남동(정면)
    mb = MB(); gran = mat_flat('#d9d4c8'); white = mat_flat('#ebe8e0'); Z0 = 1.4
    pod = poly.buffer(0)  # 기단 = OSM 윤곽(1.4 m)
    for g in parts(pod):
        g = orient(g, 1.0); capf(mb, g, lambda x, y: Z0, mat_flat('#cfc8b9')); skin(mb, g, 0.0, lambda x, y: Z0, mat_flat('#bdb6a7'), 1, 1)
    # 정면 계단: 기단 앞 가장자리(정면 축 위)
    ray = LineString([cen, cen - nv * 200]); hit = ray.intersection(pod.exterior)
    if not hit.is_empty:
        hp = np.array(min([hit] if hit.geom_type == 'Point' else list(getattr(hit, 'geoms', [])), key=lambda q: Point(*cen).distance(q)).coords[0])
        for k in range(5): obox(mb, hp - nv * (k + .5) * .45, ax_, 30.0, .45 / 2 + .02, 0.0, Z0 - k * .28, gran)
    # 본체(들여쌓기): 108×67, 높이 Z0+27
    body = Polygon([tuple(cen + ax_ * su * 54 + nv * sv * 33.5) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    tex = f'{TEXD}/asm.png'
    if not os.path.exists(tex):
        bay, flh = 1.8, 4.3; tw_, th_ = int(bay * 8 * RPPM), int(flh * 2 * RPPM); im = Image.new('RGB', (tw_, th_), '#dcd7cc'); d = ImageDraw.Draw(im)
        for f in range(2):
            for k in range(8): x0_, y0_ = int(k * bay * RPPM), int(f * flh * RPPM); d.rectangle([x0_ + 9, y0_ + 22, x0_ + int(bay * RPPM) - 9, y0_ + int(flh * RPPM) - 26], fill='#46525e'); d.line([(x0_ + int(bay * RPPM / 2), y0_ + 22), (x0_ + int(bay * RPPM / 2), y0_ + int(flh * RPPM) - 26)], fill='#9aa3a8', width=2)
        im.save(tex)
    skin(mb, orient(body, 1.0), Z0, lambda x, y: Z0 + 27.0, mat_tex(tex, 'asm'), 1.8 * 8, 4.3 * 2)
    fc = cen - nv * 33.6  # 정면 가운데 갈색 격자(두 기둥 사이 한 칸) + 아래 유리 현관
    grille = f'{TEXD}/asm_g.png'
    if not os.path.exists(grille):
        im = Image.new('RGB', (128, 128), '#6b4f3a'); d = ImageDraw.Draw(im)
        for k in range(0, 128, 8): d.line([(k, 0), (k, 128)], fill='#4a3628', width=2); d.line([(0, k), (128, k)], fill='#4a3628', width=1)
        im.save(grille)
    gm_ = mat_tex(grille, 'asm_g')
    for s_, z0_, z1_, m_ in ((1, Z0 + 7.0, Z0 + 26.0, gm_), (1, Z0, Z0 + 7.0, mat_flat('#3d4c58'))):
        p0, p1 = fc - ax_ * 8.0, fc + ax_ * 8.0; mb.face([(*p0, z0_), (*p1, z0_), (*p1, z1_), (*p0, z1_)], m_, [(0, 0), (4, 0), (4, (z1_ - z0_) / 4), (0, (z1_ - z0_) / 4)])
    # 열주 24: 앞·뒤 8, 양옆은 모서리 포함 6
    ZC = 32.0; us = np.linspace(-59.0, 59.0, 8); vs = np.linspace(-38.9, 38.9, 6); cols = set()
    for u in us:
        for sv in (-1, 1): cols.add((round(u, 2), round(sv * 38.9, 2)))
    for v in vs:
        for su in (-1, 1): cols.add((round(su * 59.0, 2), round(v, 2)))
    assert len(cols) == 24
    for u, v in cols: p_ = cen + ax_ * u + nv * v; mb.cyl((p_[0], p_[1], Z0), 1.55, ZC - Z0, white, n=8)  # 팔각 기둥
    # 평판 처마(엔태블러처) + 밑면 띠
    obox(mb, cen, ax_, 62.5, 41.5, ZC, ZC + 4.5, white, mat_flat('#cfccc4'))
    for su, sv, hx, hy in ((0, 1, 62.2, .45), (0, -1, 62.2, .45), (1, 0, .45, 40.3), (-1, 0, .45, 40.3)): obox(mb, cen + ax_ * su * 61.75 + nv * sv * 40.75, ax_, hx, hy, ZC + 4.5, ZC + 5.4, white, mat_flat('#efece6'))   # 지붕 난간
    obox(mb, cen, ax_, 61.0, 40.0, ZC - .6, ZC, mat_flat('#c9c4b8'))
    obox(mb, cen, ax_, 54, 33.5, Z0 + 27.0, ZC - .6, mat_flat('#d2cdc2'))   # 본체 위와 처마 사이 벽
    # 돔: 흰 받침 2단 + 청록 동판 반구(리브)
    RT = ZC + 4.5; mb.cyl((cen[0], cen[1], RT), 32.0, 2.4, white, mat_flat('#e2ded4'), n=48); mb.cyl((cen[0], cen[1], RT + 2.4), 29.6, 1.4, white, mat_flat('#e2ded4'), n=48)
    zb_ = RT + 3.8; Rb, Hd, NS = 29.0, 17.0, 32; prev = None; dc = [mat_flat('#7fbcab'), mat_flat('#76b3a2')]
    for j in range(9):
        t_ = j / 8; r_ = Rb * math.cos(t_ * math.pi / 2); z_ = zb_ + Hd * math.sin(t_ * math.pi / 2)
        ring = [(cen[0] + r_ * math.cos(2 * math.pi * k / NS), cen[1] + r_ * math.sin(2 * math.pi * k / NS), z_) for k in range(NS)]
        if prev:
            for k in range(NS): mb.face([prev[k], prev[(k + 1) % NS], ring[(k + 1) % NS], ring[k]], dc[k % 2])
        prev = ring
    for k in range(0, NS, 2):  # 리브 선
        pts_ = [(cen[0] + Rb * math.cos(t_ * math.pi / 2) * 1.004 * math.cos(2 * math.pi * k / NS), cen[1] + Rb * math.cos(t_ * math.pi / 2) * 1.004 * math.sin(2 * math.pi * k / NS), zb_ + Hd * math.sin(t_ * math.pi / 2)) for t_ in np.linspace(0, .97, 7)]
        for q0, q1 in zip(pts_[:-1], pts_[1:]): beam(mb, q0, q1, .35, mat_flat('#9fd0c0'))
    mb.cyl((cen[0], cen[1], zb_ + Hd - .2), 1.6, .9, white, n=12)
    mb.build('b_asm', idx)
    return poly

import bmesh
def smooth_obj(o, deg=30.0):
    """꼭짓점을 용접하고 deg° 미만으로 꺾인 이음은 부드럽게(곡면), 그 이상은 날카롭게(모서리) 음영."""
    if o is None or o.type != 'MESH': return
    me = o.data; bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.003); bm.to_mesh(me); bm.free()
    me.shade_smooth(); me.set_sharp_from_angle(angle=math.radians(deg)); me.update()
# [랜드마크 개선] 사진 대조판 빌더(lm_build.py)가 위의 b63·assembly·hyundai·church 등을 덮어쓴다
exec(compile(open(HERE + '/lm_build.py', encoding='utf-8').read(), HERE + '/lm_build.py', 'exec'))
if AREA != HERE: exec(compile(open(AREA + '/lm_build.py', encoding='utf-8').read(), AREA + '/lm_build.py', 'exec'))   # 지역 빌더가 위 공용 빌더·표(LMC, LMB, LMN …)를 고쳐 쓴다
# ---------- 건물 ----------
LMP = {k: unary_union([P(r) for r in v['rings']]).buffer(1.5) for k, v in S['landmarks'].items()}
OFFK = ('office', 'commercial', 'retail', 'hotel', 'public', 'government', 'yes', 'part', 'mixed_use', 'bank')
APTK = ('apartments', 'residential', 'dormitory', 'officetel')

from collections import Counter; cnt = Counter()
CIVIC = {'국회의원회관': '#d6d0c2', '국회도서관': '#d9d3c5', '국회의정관': '#d4cec0', '국회소통관': '#d8d4ca', '국회박물관': '#d6d0c2', 'KRX한국거래소서울사무소': '#cfcabd'}
ASMP = LMP.get('assembly'); PARKP = unary_union([P(a['rings']) for a in AR.get('grass', []) if a['name'] in PARKN] + [Point(0, 0).buffer(.01)])
P63N = LMP['63'].buffer(30) if '63' in LMP else None
GOLD63 = dict(glass='#c9a24c', span='#a9833a', mull='#7d5f26', flh=3.9, bay=1.5, top='flat', heli=False)
for i, b in enumerate(S['buildings']):
    poly = P(b['rings'])
    if poly.is_empty: continue
    c = poly.centroid.coords[0]
    if not inwin(c, b['h'] + 30, max(Point(c).distance(Point(q)) for q in poly.exterior.coords)): continue   # [3차] 반경 = 중심에서 가장 먼 꼭짓점(√면적은 긴 건물에서 짧아 이웃 타일에서 잘렸음)
    idx = 10000 + i; lm = next((k for k, g in LMP.items() if g.contains(Point(c))), None)
    if lm == 'assembly': continue  # 본관 전용 모델이 기단(OSM 윤곽)까지 대신한다
    if lm == '63' and b['h'] > 20: continue
    lk = b.get('lmk'); nm = b['name']
    if lm is None and b['h'] <= 30 and P63N is not None and P63N.contains(Point(c)): lm = '63'   # 63빌딩 저층부(OSM 파트 15 m, 본체에서 6 m)
    if lm == '63': b63_podium(b, idx); META[idx] = 'landmark:63_podium'; cnt['landmark'] += 1   # 63빌딩 저층부도 금색 유리(사진)
    elif lm in LMC and b['h'] >= 0.5 * (S['landmarks'][lm]['h'] or 0): LMB.get(lm, tower)(b, idx, LMC[lm]); META[idx] = 'landmark:' + lm; cnt['landmark'] += 1
    elif lm == 'lg': lg_low(b, idx); META[idx] = 'landmark:lg'; cnt['landmark'] += 1   # [랜드마크 2차] 두 동 사이 저층부(짙은 유리 지붕)
    elif lk == 'hyundai': hyundai(b, idx); META[idx] = 'landmark:hyundai'; cnt['landmark'] += 1
    elif lk == 'church': church(b, idx); META[idx] = 'landmark:church'; cnt['landmark'] += 1
    elif lk == 'kbs':
        bb = dict(b, h=28.0 if b['src'] not in ('height', 'levels') else b['h'])  # 높이 태그 없음 → 6층 28 m 추정
        finwall_bld(bb, idx, '#e9e6de', '#3c4852', '#f6f4ee', bay=2.8, flh=4.4, extra=lambda mb, p, h: lattice_tower(mb, mrr_axes(p)[0], h, 46.0, 3.2, .7)); META[idx] = 'landmark:kbs'; cnt['landmark'] += 1
    elif nm in LMN: LMN[nm][0](b, idx); META[idx] = LMN[nm][1]; cnt['landmark'] += 1
    elif nm in CIVIC: finwall_bld(b, idx, CIVIC[nm], '#46515b', shade(CIVIC[nm], 1.08), extra=CIVX.get(nm)); META[idx] = 'landmark:' + nm; cnt['landmark'] += 1
    elif nm.startswith('IFC mall'): glass_pav(b, idx); META[idx] = 'landmark:ifc_gate'; cnt['landmark'] += 1
    elif b['kind'] in ('roof', 'hut', 'pavilion') and PARKP.contains(Point(c)): pavilion(b, idx, 'jeong' if (b['kind'] == 'hut' or nm.endswith('정') or (b['kind'] == 'roof' and poly.area < 60 and nm)) else 'canopy'); META[idx] = 'park_pavilion'; cnt['pavilion'] += 1
    elif b['h'] >= 45 and b['kind'] not in APTK[:2]: tower(b, idx); META[idx] = 'tower'; cnt['tower'] += 1
    elif b['kind'] in APTK and b['lv'] >= 6: apartment(b, idx); META[idx] = 'apartment'; cnt['apartment'] += 1
    elif b['kind'] == 'train_station' or b['kind'] == 'station': finwall_bld(dict(b, h=max(b['h'], 9.0)), idx, '#d7d9db', '#4d6273', '#eef0f1', bay=3.0, flh=4.5); META[idx] = 'station_building'; cnt['station'] += 1
    else:
        rr = random.Random(b['seed']); k = b['kind']
        fac = 'office_stone' if k in ('office', 'bank') else 'civic_stone' if k in ('public', 'government', 'school', 'university', 'college', 'kindergarten', 'hospital', 'church') else 'resi_tower' if k in APTK else rr.choice(['brick', 'stucco', 'stucco'])
        modern({'rings': b['rings'], 'h': max(3.0, b['h']), 'seed': b['seed'], 'fac': fac, 'flh': 3.3, 'storefront': k in ('commercial', 'retail', 'yes', 'synthetic') and rr.random() < .45, 'parapet': True,
                'penthouse': b['h'] > 9 and rr.random() < .35, 'roofcol': rr.choice(['roof_green', 'roof_green', 'roof_concrete', 'roof_concrete', 'roof_dark'])}, idx)
        META[idx] = 'lowrise_synthetic' if b['src'] == 'synthetic' else 'lowrise'; cnt['synthetic' if b['src'] == 'synthetic' else 'lowrise'] += 1
    o_ = bpy.data.objects.get('b%d' % idx)
    if o_ is not None and b['h'] > 0 and WATER.contains(Point(c)): o_.location.z = -1.2   # 물 위(부잔교) 건물은 수면 +0.6 m 에
    smooth_obj(o_)
if '63' in S['landmarks']:
    c63 = P(S['landmarks']['63']['rings'][0]).centroid.coords[0]
    if inwin(c63, 260, 40): b63(S['landmarks']['63'], 9063); smooth_obj(bpy.data.objects.get('b63'), 35.0); META[9063] = 'landmark:63'; cnt['63'] += 1
if 'assembly' in S['landmarks']:
    ca = P(S['landmarks']['assembly']['rings'][0]).centroid.coords[0]
    if inwin(ca, 60, 110): assembly(S['landmarks']['assembly'], 9100); META[9100] = 'landmark:assembly'; cnt['assembly'] += 1
# ---------- [2차] 역: 지하철 출입구 캐노피(유리·금속, 곡면 지붕), 지상 승강장 + 승강장 지붕 ----------
TR = S.get('transit', {}); nst = 0
for k_, en in enumerate(TR.get('entrances', [])):
    x, y = en['xy']
    if not inwin((x, y), 4, 6): continue
    mb = MB(); ax_ = np.array([math.cos(en['ang']), math.sin(en['ang'])]); nv = np.array([-ax_[1], ax_[0]]); c_ = np.array([x, y])
    gl = mat_flat('#8fb0c4'); fr = mat_flat('#5d646b')
    for sv in (-1, 1): obox(mb, c_ + nv * sv * 1.75, ax_, 3.6, .08, 0, 1.1, fr); mb.face([(*(c_ + nv * sv * 1.75 - ax_ * 3.6), 1.1), (*(c_ + nv * sv * 1.75 + ax_ * 3.6), 1.1), (*(c_ + nv * sv * 1.75 + ax_ * 3.6), 2.7), (*(c_ + nv * sv * 1.75 - ax_ * 3.6), 2.7)], gl)
    prof_ = [(1.9 * math.cos(math.pi * j / 6), 2.7 + .7 * math.sin(math.pi * j / 6)) for j in range(7)]
    for (v0, z0), (v1, z1) in zip(prof_[:-1], prof_[1:]):
        a0, a1 = c_ - ax_ * 3.8, c_ + ax_ * 3.8; mb.face([(*(a0 + nv * v1), z1), (*(a1 + nv * v1), z1), (*(a1 + nv * v0), z0), (*(a0 + nv * v0), z0)], mat_flat('#a9b9c4'))
    obox(mb, c_ - ax_ * 4.4 + nv * 1.2, ax_, .12, .12, 0, 3.4, fr); obox(mb, c_ - ax_ * 4.4 + nv * 1.2, ax_, .5, .12, 3.4, 4.2, mat_flat('#2f6fb3'))  # 역 표지 기둥(색 추정)
    mb.build('st%d' % k_, 9200 + k_); META[9200 + k_] = 'station_entrance:%s %s번' % (en['station'], en['ref']); nst += 1
for k_, pf in enumerate(TR.get('platforms', [])):
    ln = LineString(pf['pts'])
    if not inwin(ln.centroid.coords[0], 6, ln.length / 2 + 10): continue
    g = Polygon(pf['pts']).buffer(0) if pf['closed'] and len(pf['pts']) >= 4 else ln.buffer(3.2, cap_style=2)
    g = max(parts(g), key=lambda q: q.area) if parts(g) else None
    if g is None or g.area < 10: continue
    g = orient(g, 1.0); mb = MB(); skin(mb, g, 0.0, lambda x, y: 1.1, mat_flat('#b5b2aa'), 1, 1); capf(mb, g, lambda x, y: 1.1, mat_flat('#cfccc4'))
    c_, ax_, Lx_, Ly_, _ = mrr_axes(g); ro = mat_flat('#9aa3a8')  # 승강장 지붕(기둥 + 얇은 지붕, 길이는 승강장의 70%로 추정)
    for s_ in np.linspace(-Lx_ * .35, Lx_ * .35, max(2, int(Lx_ * .7 / 12))): p_ = c_ + ax_ * s_; mb.cyl((p_[0], p_[1], 1.1), .15, 3.2, mat_flat('#6f777e'), n=6)
    obox(mb, c_, ax_, Lx_ * .36, max(1.6, Ly_ / 2 + .8), 4.3, 4.6, ro, mat_flat('#b6bec3'))
    mb.build('pf%d' % k_, 9400 + k_); META[9400 + k_] = 'station_platform'; nst += 1
cnt['transit'] = nst
print('buildings', dict(cnt), 't', round(time.time() - T0, 1), flush=True)

# ---------- 교량. [2차] 높이는 prep 의 교량 노드 그래프 값(nz, 공유 노드 = 같은 높이)을 호 길이로 보간. 교량별 형식(근거·추정은 NOTES) ----------
WPREP = WATER.buffer(0); shapely.prepare(WPREP); WL = -1.8  # 수면 높이(둔치 = 0)
ISLANDS = [Polygon(r.coords) for g in parts(WATER) for r in g.interiors if 5e4 < Polygon(r.coords).area < 5e5]   # 밤섬 등 강 속 섬
def bstyle(r):
    n_ = r['name']
    if '원효' in n_ or n_ == '여의대방로': return 'wonhyo'   # [랜드마크 개선] OSM 도로 이름: 원효대교 = 여의대방로, 마포대교 = 여의대로·마포대로, 서강대교 = 서강로·국회대로
    if '마포' in n_ or n_ == '여의대로': return 'mapo'
    if '서강' in n_ or n_ == '국회대로': return 'seogang'
    if r['cls'] == 'rail': return 'rail'
    return 'generic'
def dens(r):
    ln = LineString(r['pts']); nd = np.array(r['pts']); seg = np.hypot(*np.diff(nd, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
    n_ = max(2, int(ln.length / 6) + 1); ss = np.linspace(0, ln.length, n_); ss = np.unique(np.r_[ss, cum]); pts = np.array([ln.interpolate(s).coords[0] for s in ss])
    z = np.interp(ss, cum, r.get('nz') or np.full(len(cum), 7.0)); return ln, ss, pts, z
# [6차] 접속부 다듬기(사용자: "교량에서 도로로 이어지는 부분이 부자연스럽다"): 교량 way 마다 난간(1 m 벽)을 양옆에 세워서, 램프·차로가 합쳐지는 곳에서는
#  이웃 상판 위를 난간이 비스듬히 가로질렀고, 땅에 내려앉은 끝에서도 난간이 뚝 끊겼다. → 이웃 교량 상판(높이 차 1.5 m 안) 위에 놓이는 난간 조각은 세우지 않고,
#  상판이 지면에 가까워지면(z 0.4→1.2 m) 난간 높이를 0→1 m 로 줄인다.
BRP = {}
for ri, r in enumerate(S['roads']):
    if not r['bridge'] or r['cls'] == 'rail': continue
    ln0_ = LineString(r['pts'])
    if not ln0_.intersects(GREG.buffer(80)): continue
    w_ = r['w']
    if r.get('river', ln0_.intersection(WPREP).length > 100) and r['cls'] == 'major' and w_ < 12: w_ = 14.0
    ln_, ss_, pts_, z_ = dens(r); pg_ = ln_.buffer(max(0.5, w_ / 2 - 0.35), cap_style=2); shapely.prepare(pg_); BRP[ri] = (pg_, ln_, ss_, z_, ln_.buffer(w_ / 2 + 1.5))
BRNB = {ri: [rj for rj in BRP if rj != ri and BRP[rj][0].intersects(BRP[ri][4])] for ri in BRP}
def rail_ok(ri, x, y, zc):
    for rj in BRNB.get(ri, ()):
        pg_, ln_, ss_, z_, _ = BRP[rj]
        if shapely.contains_xy(pg_, x, y) and abs(float(np.interp(ln_.project(Point(x, y)), ss_, z_)) - zc) < 1.5: return False
    return True
def rail_h(z_): return float(min(1.0, max(0.0, (z_ - 0.4) / 0.8)))
nbr = 0; ARCH = []
for ri, r in enumerate(S['roads']):
    if not r['bridge']: continue
    ln = LineString(r['pts'])
    if not ln.intersects(GREG.buffer(80)): continue
    river = r.get('river', ln.intersection(WPREP).length > 100); st = bstyle(r); w = r['w']
    if river and r['cls'] == 'major' and w < 12: w = 14.0
    ln, ss, pts, z = dens(r)
    tg = np.gradient(pts, axis=0); tg /= np.maximum(np.hypot(tg[:, 0], tg[:, 1]), 1e-6)[:, None]; nm = np.stack([-tg[:, 1], tg[:, 0]], 1)
    L_ = pts + nm * w / 2; Rr = pts - nm * w / 2
    span = {'wonhyo': 100.0, 'mapo': 60.0, 'seogang': 75.0, 'rail': 46.0}.get(st, 55.0) if river else 30.0
    piers = [s for s in np.arange(span / 2, ln.length, span)]
    dep0 = 2.8 if river and r['cls'] != 'foot' else 1.3
    def depth(s):
        if st != 'wonhyo' or not river or not piers: return dep0
        dp = min(abs(s - p) for p in piers); return 2.6 + 3.8 * max(0.0, 1 - dp / (0.42 * span)) ** 2   # 원효대교: FCM 박스거더 → 교각 쪽이 깊은 변단면(형식은 위키백과, 깊이는 추정)
    dep = np.array([depth(s) for s in ss])
    mb = MB(); topm = mat_flat('#5f6267' if r['cls'] in ('major', 'minor') else '#a8665a' if r['cls'] == 'cycle' else '#6e665c' if r['cls'] == 'rail' else '#cfc6b4')
    sidem = mat_flat({'mapo': '#a9aeb0', 'seogang': '#b9b6ae', 'rail': '#8a8f8c'}.get(st, '#b4b1a9')); botm = mat_flat('#8e8b84'); railm = mat_flat('#e2e0da')
    for k in range(len(pts) - 1):
        a0, a1, b0, b1 = L_[k], L_[k + 1], Rr[k], Rr[k + 1]; za, zb = z[k], z[k + 1]; da, db = dep[k], dep[k + 1]
        mb.face([(b0[0], b0[1], za), (b1[0], b1[1], zb), (a1[0], a1[1], zb), (a0[0], a0[1], za)], topm)
        for p0, p1, fl in ((a0, a1, False), (b0, b1, True)):
            q = [(p0[0], p0[1], za - da), (p1[0], p1[1], zb - db), (p1[0], p1[1], zb), (p0[0], p0[1], za)]; mb.face(q[::-1] if fl else q, sidem)
            if r['cls'] != 'rail':
                ha, hb = rail_h(za), rail_h(zb); mo = (p0 + p1) / 2 + (nm[k] + nm[k + 1]) / 2 * (-0.6 if fl else 0.6)   # [6차] 난간 조각의 가운데에서 바깥으로 0.6 m
                if max(ha, hb) > 0.05 and rail_ok(ri, float(mo[0]), float(mo[1]), (za + zb) / 2):
                    q = [(p0[0], p0[1], za), (p1[0], p1[1], zb), (p1[0], p1[1], zb + hb), (p0[0], p0[1], za + ha)]; mb.face(q[::-1] if fl else q, railm)
        mb.face([(a0[0], a0[1], za - da), (a1[0], a1[1], zb - db), (b1[0], b1[1], zb - db), (b0[0], b0[1], za - da)], botm)
    if FINE and r['cls'] in ('major', 'minor') and w >= 6:  # 상판 차선(흰 점선)
        for k in range(len(pts) - 1):
            if (ss[k] // 4) % 2 == 0:
                for o in ([-w / 4, w / 4] if w > 12 else [0.0]):
                    p0, p1 = pts[k] + nm[k] * o, pts[k + 1] + nm[k + 1] * o; d_ = (p1 - p0) * 0.6
                    mb.face([(p0[0] - nm[k][0] * .08, p0[1] - nm[k][1] * .08, z[k] + .02), (p0[0] + d_[0] - nm[k][0] * .08, p0[1] + d_[1] - nm[k][1] * .08, z[k + 1] + .02),
                             (p0[0] + d_[0] + nm[k][0] * .08, p0[1] + d_[1] + nm[k][1] * .08, z[k + 1] + .02), (p0[0] + nm[k][0] * .08, p0[1] + nm[k][1] * .08, z[k] + .02)], mat_flat('#ecece6'))
    if st == 'rail' and river:  # 철교: 연한 녹색 강 트러스(한강철교, 동작대교에서 찍힌 사진의 색) — 범위에 들 때만 보인다
        tm = mat_flat('#8fb3a0'); TH_ = 7.0
        for side in (L_, Rr):
            for k in range(0, len(pts) - 1):
                p0, p1 = side[k], side[k + 1]; beam(mb, (*p0, z[k] + TH_), (*p1, z[k + 1] + TH_), .5, tm)
                if k % 2 == 0: beam(mb, (*p0, z[k]), (*p1, z[k + 1] + TH_), .35, tm); beam(mb, (*p0, z[k]), (*p0, z[k] + TH_), .35, tm)
    for s in piers:
        k = int(np.argmin(np.abs(ss - s)))
        zt = z[k] - dep[k]
        if zt < 1.0: continue
        zb_ = WL - .5 if WPREP.contains(Point(*pts[k])) else -0.3; pm = mat_flat('#d8d6cf' if st == 'wonhyo' else '#a7a49c'); ang_ = tg[k]
        if st in PIERB: PIERB[st](mb, pts[k], tg[k], nm[k], w, zb_, zt, pm)   # [랜드마크 개선] 사진 대조 교각(lm_build.py)
        elif st == 'wonhyo':  # 원효대교: 위가 벌어진 흰 벽식 교각 + 둥근 기초(사진)
            taper(mb, pts[k], ang_, 1.6, w * .18, 1.8, w * .42, zb_, zt - 2.0, pm); taper(mb, pts[k], ang_, 1.8, w * .42, 2.0, w * .5, zt - 2.0, zt, pm)
            if zb_ < 0: mb.cyl((pts[k][0], pts[k][1], WL - .6), w * .32, .9, mat_flat('#c2a77d'), n=20)
        elif st == 'mapo':  # 마포대교: 둥근 기둥 2 + 머리 보(추정)
            for o in (-w * .28, w * .28): p0 = pts[k] + nm[k] * o; mb.cyl((p0[0], p0[1], zb_), 1.4, zt - 1.6 - zb_, pm, n=12)
            obox(mb, pts[k], tg[k], 1.6, w * .45, zt - 1.6, zt, pm)
        else:
            for o in ((-w * .28, w * .28) if w > 9 else (0.0,)):
                p0 = pts[k] + nm[k] * o; mb.cyl((p0[0], p0[1], zb_), 1.3 if river else .7, zt - zb_, pm, n=10)
    if st == 'seogang' and r['cls'] == 'major':  # 서강대교: 밤섬 위 닐센 아치(붉은색 — 사진). 아치 높이 28 m 는 추정
        for isl in ISLANDS:
            seg = ln.intersection(isl)
            if seg.is_empty or seg.length < 40: continue
            mid = ln.project(seg.centroid); ARCH.append((ri, mid, ln, ss, z, w))
    mb.build('br%d' % ri, 20000 + ri); META[20000 + ri] = 'bridge:' + (r['name'] or st); nbr += 1
for ri, mid, ln, ss, z, w in ARCH[:1] if ARCH else []:  # 아치 한 벌(양방향 상판을 함께 걸치도록 중심 상판 기준 ±(w/2+3))
    mb = MB(); am = mat_flat('#c8382c'); SPN, RISE = 150.0, 28.0; hm_ = mat_flat('#e9e6e0')
    sa = np.linspace(mid - SPN / 2, mid + SPN / 2, 25)
    for side in (-1, 1):
        prev = None
        for j, s_ in enumerate(sa):
            p_ = np.array(ln.interpolate(s_).coords[0]); q_ = np.array(ln.interpolate(min(ln.length, s_ + 1)).coords[0]) - p_; q_ /= (np.hypot(*q_) or 1); n_ = np.array([-q_[1], q_[0]])
            t_ = (s_ - mid) / (SPN / 2); zz = np.interp(s_, ss, z) + 1.0 + RISE * (1 - t_ * t_); off = (w / 2 + 3.0) * (1 - .55 * (1 - t_ * t_))   # 두 아치가 위로 갈수록 안쪽으로 기울어 모임
            cur = np.array([*(p_ + n_ * side * off), zz])
            if prev is not None: beam(mb, prev, cur, 1.6, am, 2.2)
            if 0 < j < len(sa) - 1 and j % 2 == 0: beam(mb, cur, np.array([*(p_ + n_ * side * (w / 2 + 3.0)), np.interp(s_, ss, z) + 1.0]), .12, hm_)
            prev = cur
    mb.build('arch_seogang', 20000 + ri); nbr += 1
print('bridges', nbr, 'arches', len(ARCH[:1]), flush=True)

# ---------- 나무(구역별 메시로 묶음, ID 30000 하나) ----------
tmb = {}; ntr = 0
for k, (x, y, r, kd) in enumerate(S['trees']):
    if not inwin((x, y), 2 + r * 2, r): continue
    key = (int(x // 120), int(y // 120)); mb = tmb.setdefault(key, MB()); tree(k, x, y, r, mb); ntr += 1
for key, mb in tmb.items(): mb.build('trees_%d_%d' % key, 30000)
META[30000] = 'tree'; print('trees', ntr, 't', round(time.time() - T0, 1), flush=True)

# ---------- 지면 판 ----------
# [2차] 둔치(z=0)와 강 수면(z=WL)을 나누고, 물가에 호안 경사면(사석) 또는 계단(보행 광장 앞)을 놓는다. 모두 같은 지면 텍스처(월드 UV).
mb = MB(); gmat = mat_tex(GPATH, 'ground')
uvw = lambda x, y: ((x - gx0) / (gx1 - gx0), (y - gy0) / (gy1 - gy0))
mb.face([(gx0, gy0, WL), (gx1, gy0, WL), (gx1, gy1, WL), (gx0, gy1, WL)], gmat, [(0, 0), (1, 0), (1, 1), (0, 1)])
LAND = GBOX.difference(WATERc)
for g in parts(LAND):
    for t in shapely.constrained_delaunay_triangles(g).geoms:
        q = list(orient(t, 1.0).exterior.coords)[:-1]; mb.face([(x, y, 0.0) for x, y in q], gmat, [uvw(x, y) for x, y in q])
STEPP = STEPZ.buffer(1.0); shapely.prepare(STEPP); nsk = 0
NOSK = globals().get('NOSKIRT')   # 지역 빌더가 둘레를 직접 세우는 구덩이(광장의 내리막 계단 등): 이 안의 물가 변에는 비탈을 두르지 않는다
for g in parts(WATERc):
    g = orient(g, 1.0)
    for ring in [g.exterior] + list(g.interiors):
        cc = list(ring.coords)[:-1]; n_ = len(cc)
        if n_ < 3: continue
        en = []
        for i in range(n_):   # 변 법선(왼쪽 = 물 쪽)
            a_, b_ = cc[i], cc[(i + 1) % n_]; ex_, ey_ = b_[0] - a_[0], b_[1] - a_[1]; L_ = math.hypot(ex_, ey_) or 1.0
            en.append((-ey_ / L_, ex_ / L_))
        vn = []
        for i in range(n_):   # 꼭짓점 마이터 법선 — 이웃 변의 단면이 꼭짓점에서 맞물려 틈(검은 세로줄)이 안 생긴다
            (x0_, y0_), (x1_, y1_) = en[i - 1], en[i]; mx_, my_ = x0_ + x1_, y0_ + y1_; ml = math.hypot(mx_, my_)
            if ml < 1e-6: vn.append((x1_, y1_)); continue
            mx_, my_ = mx_ / ml, my_ / ml; c_ = max(.5, mx_ * x1_ + my_ * y1_); vn.append((mx_ / c_, my_ / c_))
        for i in range(n_):
            a_, b_ = cc[i], cc[(i + 1) % n_]; ex_, ey_ = b_[0] - a_[0], b_[1] - a_[1]; L_ = math.hypot(ex_, ey_)
            if L_ < .05: continue
            if abs(a_[0] - b_[0]) < 1e-6 and (abs(a_[0] - GBOX.bounds[0]) < 6 or abs(a_[0] - GBOX.bounds[2]) < 6): continue   # 텍스처 경계(잘린 변)
            if abs(a_[1] - b_[1]) < 1e-6 and (abs(a_[1] - GBOX.bounds[1]) < 6 or abs(a_[1] - GBOX.bounds[3]) < 6): continue
            nx_, ny_ = en[i]; na_, nb_ = vn[i], vn[(i + 1) % n_]
            mid = Point((a_[0] + b_[0]) / 2 + nx_ * 2, (a_[1] + b_[1]) / 2 + ny_ * 2)
            if NOSK is not None and NOSK.contains(mid): continue
            if STEPP.contains(mid):  # 계단식 호안: 디딤 1.375 m × 챌면 0.45 m 네 단
                prof = [(0.0, 0.0)]
                for k in range(4): prof += [((k + 1) * REV / 4, k * WL / 4), ((k + 1) * REV / 4, (k + 1) * WL / 4)]
            else: prof = [(0.0, 0.0), (REV * .35, WL * .45), (REV, WL)]   # 사석 경사(위는 완만, 아래는 급함)
            for (o0, z0), (o1, z1) in zip(prof[:-1], prof[1:]):
                pa0, pb0 = (a_[0] + na_[0] * o0, a_[1] + na_[1] * o0), (b_[0] + nb_[0] * o0, b_[1] + nb_[1] * o0); pa1, pb1 = (a_[0] + na_[0] * o1, a_[1] + na_[1] * o1), (b_[0] + nb_[0] * o1, b_[1] + nb_[1] * o1)
                if abs(o1 - o0) < 1e-6 and abs(z1 - z0) < 1e-6: continue
                q = [(*pa0, z0), (*pb0, z0), (*pb1, z1), (*pa1, z1)]; mb.face(q, gmat, [uvw(p[0], p[1]) for p in q]); nsk += 1
mb.build('ground', 1)
# 물 위 부잔교·선착장 갑판(수면 +0.6 m)
for g, a in areas('pier'):
    if not WPREP.contains(g.representative_point()): continue
    mb = MB(); g = orient(g, 1.0); skin(mb, g, WL - .3, lambda x, y: WL + .6, mat_flat('#7b6e5c'), 1, 1); capf(mb, g, lambda x, y: WL + .6, mat_flat('#9a8a70')); mb.build('pier_%d' % nsk, 1); nsk += 1
print('ground mesh skirts', nsk, flush=True)

# ---------- 카메라(판 전체가 같은 카메라 평면 → 창마다 깊이가 이어진다) ----------
sc = bpy.context.scene
BC = CAM.unproj(CAM.W / 2, CAM.H / 2, 0); CREF = np.array(BC) - VD * 3000.0
bcx, bcy = CAM.SX0 + CAM.W * PX0 / 2, CAM.SY1 - CAM.H * PX0 / 2
wcx, wcy = CAM.SX0 + (X0 + WX1) / 2 * PX0, CAM.SY1 - (Y0 + WY1) / 2 * PX0
dz = [(np.array(CAM.unproj(X, Y, zz)) - CREF) @ VD for X in (0, CAM.W) for Y in (0, CAM.H) for zz in (0, 360)]
DZ0, DZS = math.floor(min(dz) - 20), float(os.environ.get('P3D_DZS', 0.05))   # 화면 세로가 약 2100 m 를 넘는 판은 깊이 단위를 키운다(16비트 한도)
assert (max(dz) - DZ0) / DZS < 65000, 'depth range'
cd = bpy.data.cameras.new('cam'); cd.type = 'ORTHO'; cd.ortho_scale = max(WW, WH) * PXR; cd.clip_start = 1; cd.clip_end = 9000
co = bpy.data.objects.new('cam', cd); sc.collection.objects.link(co); sc.camera = co
co.rotation_euler = (math.radians(55), 0, math.radians(CAM.b['theta']))
co.location = Vector(CREF + EX * (wcx - bcx) + EY * (wcy - bcy))
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 3.6; sd.angle = math.radians(1.5)
so = bpy.data.objects.new('sun', sd); so.rotation_euler = (math.radians(50), 0, math.radians(CAM.b['theta'] - 73)); sc.collection.objects.link(so)  # 경복궁 판과 같은 카메라 대비 해 방향
w = bpy.data.worlds.new('w'); w.use_nodes = True; bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (1, 1, 1, 1); bg.inputs[1].default_value = 0.7; sc.world = w
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(os.environ.get('P3D_SPP', 64)); sc.cycles.use_denoising = False; sc.cycles.filter_width = 0.6
sc.cycles.device = 'CPU'
if os.environ.get('P3D_THREADS'): sc.render.threads_mode = 'FIXED'; sc.render.threads = int(os.environ['P3D_THREADS'])  # [3차] 병렬 타일 렌더에서 프로세스당 스레드 고정
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = WW, WH, 100
sc.view_settings.view_transform = 'Standard'; sc.render.image_settings.file_format = 'PNG'
OP = OUT if os.path.isabs(OUT) else f'{HERE}/{OUT}'
os.makedirs(os.path.dirname(OP) or '.', exist_ok=True)
sc.render.filepath = OP + '.png'
print('scene built', 't', round(time.time() - T0, 1), flush=True)
if SAVE_BLEND:
    sys.path.insert(0, os.path.join(HERE, '..', 'common')); import blend_save
    blend_save.save(SAVE_BLEND, dict(map='yeouido', board=BOARD, board_def=CAM.b, window_6p25=[X0, Y0, WX1, WY1], px_m=PXR, render_px=[WW, WH], samples=sc.cycles.samples,
                    ground_texel_m=GTEX, pxgrid=os.environ.get('P3D_PXGRID', '1'), depth=dict(z0=DZ0, step=DZS, cam_ref=CREF.tolist(), view_dir=VD.tolist()), meta=META),
                    readme=open(os.path.join(HERE, '..', 'common', 'BLEND-README.md'), encoding='utf-8').read())
    if NO_RENDER: sys.exit(0)
bpy.ops.render.render(write_still=True)
print('beauty done', 't', round(time.time() - T0, 1), flush=True)
json.dump({'ids': META, 'board': BOARD, 'board_def': CAM.b, 'window_6p25': [X0, Y0, WX1, WY1], 'render_px_m': PXR, 'size': [WW, WH], 'id': 'pass_index = R*256+G',
           'depth': {'formula': 'view_z_m = z0 + (R*256+G)*step, 65535 = 없음 아님(배경 없음: 지면이 끝까지 덮음)', 'z0': DZ0, 'step': DZS, 'cam_ref': CREF.tolist(), 'view_dir': VD.tolist()},
           'counts': dict(cnt, bridges=nbr, trees=ntr)}, open(OP + '_meta.json', 'w'), ensure_ascii=False)
if os.environ.get('P3D_PASS', '1') == '1':  # gen.py 와 같은 방식: ID(R=상위, G=하위 바이트), 깊이(16비트를 R,G 로)
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
        cdn = nt.nodes.new('ShaderNodeCameraData'); a = nt.nodes.new('ShaderNodeMath'); a.operation = 'SUBTRACT'; nt.links.new(cdn.outputs['View Z Depth'], a.inputs[0]); a.inputs[1].default_value = float(DZ0)
        d_ = nt.nodes.new('ShaderNodeMath'); d_.operation = 'DIVIDE'; nt.links.new(a.outputs[0], d_.inputs[0]); d_.inputs[1].default_value = DZS
        r_ = nt.nodes.new('ShaderNodeMath'); r_.operation = 'ROUND'; nt.links.new(d_.outputs[0], r_.inputs[0]); return r_.outputs[0]
    sc.cycles.samples = 1; sc.cycles.filter_width = 0.01; sc.view_settings.view_transform = 'Raw'; bg.inputs[1].default_value = 0.0; so.hide_render = True
    sc.cycles.max_bounces = 0; sc.render.dither_intensity = 0.0
    for nm, bf in (('id', b_id), ('z', b_z)):
        sc.view_layers[0].material_override = ovr(nm, bf); sc.render.filepath = f'{OP}_{nm}.png'; bpy.ops.render.render(write_still=True)
print('done', 't', round(time.time() - T0, 1), flush=True)
