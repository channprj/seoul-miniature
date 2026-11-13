# 테헤란로 장면 보충: ../yeouido/prep.py 가 만든 scene.json 을 읽어 판 T 에 맞게 고쳐 쓴다.
# 사용(작업 폴더 = osm/ 과 scene.json 이 있는 곳): python prep_extra.py
#   건물을 판 둘레로 줄이고, 큰길가 건물의 높이 추정을 올리고, 랜드마크 윤곽·지하철 출입구·보행 광장·왕릉(봉분, 홍살문)·교량 높이를 더한다.
import json, math, os, random, sys, zlib
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open('scene.json'))
if S.get('extra'): sys.exit('scene.json 은 이미 보충됐다. prep.py 부터 다시 돌릴 것')
os.environ['P3D_ORG'] = json.dumps(S['org'])
_src = open(os.path.join(HERE, '..', 'yeouido', 'prep.py'), encoding='utf-8').read()
exec(compile(_src[:_src.index('# ---------------- 건물')], 'prep.py', 'exec'))   # tm5186, xy, L, num, waypoly, rings (clsdump.py 와 같은 방식)
sys.path.insert(0, HERE); from cam import Cam
C = Cam('T')
BOARD = Polygon([C.unproj(X, Y, 0)[:2] for X, Y in ((0, 0), (C.W, 0), (C.W, C.H), (0, C.H))])
REG = BOARD.buffer(420)   # 도로·교량을 남길 범위

# ---- 건물 보충: OSM 에 건물이 비어 있는 블록을 Overture 건물 테마의 비 OSM 풋프린트(East Asian Buildings, CC BY 4.0)로 채운다. 높이는 면적으로 추정 ----
B = S['buildings']
OV = 'osm/overture_buildings.geojson'   # uvx overturemaps download --bbox=서,남,동,북 -f geojson --type=building -o osm/overture_buildings.geojson
if os.path.exists(OV):
    have = [Polygon(b['rings'][0]).buffer(0) for b in B]; htree = STRtree(have); nadd = 0
    for f in json.load(open(OV))['features']:
        pr = f['properties']
        if (pr.get('sources') or [{}])[0].get('dataset') == 'OpenStreetMap' or f['geometry']['type'] != 'Polygon': continue
        lon, lat = np.array(f['geometry']['coordinates'][0]).T; x, y = tm5186(lon, lat); p = Polygon(np.stack([x, y], 1)).buffer(0).simplify(.4)
        if p.geom_type != 'Polygon' or p.area < 35 or sum(have[k].intersection(p).area for k in htree.query(p)) > .12 * p.area: continue
        osm = 'o' + f['id'][:8]; rnd = random.Random(zlib.crc32(osm.encode())); ar = p.area
        fl = rnd.choice([1, 2, 2, 3] if ar < 90 else [2, 3, 3, 4, 5] if ar < 300 else [4, 5, 6, 7] if ar < 1000 else [4, 6, 8] if ar < 3000 else [2, 3, 4])
        B.append({'osm': osm, 'rings': [np.round(np.array(p.exterior.coords), 2).tolist()], 'h': round(fl * 3.6, 1), 'min_h': 0.0, 'lv': fl, 'src': 'est_overture', 'kind': 'yes', 'part': False,
                  'name': '', 'name_en': '', 'colour': '', 'area': round(ar, 1), 'seed': zlib.crc32(osm.encode()) % 100000}); nadd += 1
    if nadd:   # 채운 건물 자리의 나무(prep 이 빈 땅으로 보고 놓은 것)를 뺀다
        import shapely; fu = unary_union([Polygon(b['rings'][0]).buffer(1.2) for b in B[-nadd:]]); T = np.array(S['trees'])
        S['trees'] = [t for t, k in zip(S['trees'], shapely.contains_xy(fu, T[:, 0], T[:, 1])) if not k]
    print('overture fill', nadd, 'trees', len(S['trees']))

# ---- 철거가 끝난 공사 터(GBC, 영동대로 복합환승센터)에 OSM 이 남겨 둔 옛 건물과 나무를 뺀다 ----
_site = unary_union([Polygon(a['rings'][0]).buffer(0) for a in S['areas'].get('dirt', []) if a['name'] in ('현대자동차 글로벌비즈니스센터', '영동대로복합환승센터')] + [Point(0, 0).buffer(.01)])
_n = len(B); B = [b for b in B if not _site.contains(Point(*np.array(b['rings'][0]).mean(0)))]
S['trees'] = [t for t in S['trees'] if not _site.buffer(-4).contains(Point(t[0], t[1]))]; print('cleared from sites', _n - len(B))

# ---- 건물: 화면에 걸리는 것만(바닥·꼭대기·그림자 끝 중 하나가 판 안). 건물 ID 는 10000+순번이라 수를 줄여야 교량 ID(20000+)와 겹치지 않는다 ----
_sa, _sg = math.radians(50.0), math.radians(C.b['theta'] - 73.0); SH = np.array([-math.sin(_sg) * math.tan(_sa), math.cos(_sg) * math.tan(_sa)])   # gen_area 의 해 방향
NEAR = BOARD.buffer(70)
def seen(b):
    c = np.array(b['rings'][0]).mean(0); h = b['h']
    if NEAR.contains(Point(*c)) or NEAR.contains(Point(*(c + SH * h))): return True
    X, Y = C.proj([c[0], c[1], h]); return -900 < X < C.W + 900 and -900 < Y < C.H + 900
S['buildings'] = B = [b for b in B if seen(b)]

# ---- 높이 추정 보정: 큰길가의 태그 없는 건물은 중·고층으로(강남 간선 변은 15층 안팎 업무 빌딩이 줄지어 있다. 층수는 추정) ----
MAJOR = [r for r in S['roads'] if r['hw'] in ('trunk', 'primary', 'secondary') and not r['tunnel'] and not r['bridge']]
mlines = [LineString(r['pts']) for r in MAJOR]; mtree = STRtree(mlines); nfix = 0
for b in B:
    if not b['src'].startswith('est') or b['kind'] in ('roof', 'house', 'detached', 'school', 'church', 'temple', 'parking') or b['area'] < 220: continue
    p = Polygon(b['rings'][0]); k = mtree.nearest(p); r = MAJOR[k]; d = mlines[k].distance(p) - r['w'] / 2
    if d > 14: continue
    rnd = random.Random(b['seed']); big = r['name'] in ('테헤란로', '강남대로', '영동대로')
    fl = rnd.choice([12, 14, 15, 17, 18, 20] if big and b['area'] > 500 else [8, 10, 12, 14] if big or b['area'] > 600 else [5, 6, 7, 8, 10])
    b['h'], b['lv'], b['src'] = round(fl * 3.9 + 3, 1), fl, 'est_frontage'; nfix += 1
for b in B:   # 초고층 주상복합(타워팰리스 등)은 판상형 아파트 입면이 아니라 유리 타워로 세운다
    if b['kind'] in ('apartments', 'residential') and b['h'] >= 110: b['kind'] = 'resi_tower'
print('buildings', len(B), 'frontage heights', nfix)

# ---- 랜드마크 윤곽(전용 모델·설정의 기준). 키 → OSM id 들 ----
LM = {'trade': ['w380067758', 'w637322920'] + ['w%d' % i for i in range(637098865, 637098878)], 'asem': ['w74056384'], 'parnas': ['w927603580'], 'gfc': ['w117823787'], 'db': ['w1078788202'], 'posco_e': ['w840263996'], 'posco_w': ['w466291216'],
      'gt': ['w301605795'], 'samsung_e': ['r8311185'], 'samsung_c': ['r8311184'], 'samsung_l': ['r8311183'], 'cf_e': ['w836753661'], 'cf_w': ['w836753662'], 'gs': ['w562011101'],
      'meritz': ['w379232116'], 'glass': ['w85032873'], 'wework': ['w804792366'], 'coex': ['w74013220']}
S['landmarks'] = {}
for k, ids in LM.items():
    bs = [b for b in B if b['osm'] in ids]
    if not bs: print('landmark missing', k); continue
    # h = 가장 낮은 구성 건물의 높이: gen_area 는 윤곽 안 건물 중 h 의 절반 이상인 것을 그 랜드마크 빌더로 세운다(트레이드타워의 계단꼴 파트가 모두 들게)
    S['landmarks'][k] = {'osm': ids[0], 'rings': [b['rings'] for b in bs], 'h': min(b['h'] for b in bs), 'h_top': max(b['h'] for b in bs), 'lv': max(b['lv'] for b in bs), 'name': bs[0]['name']}
print('landmarks', list(S['landmarks']))

# ---- 지하철 출입구: 가장 가까운 역 이름, 가까운 차도 방향으로 놓는다 ----
PTS = L('points')
stations = [(e['tags'].get('name', ''), Point(*map(float, tm5186(e['lon'], e['lat'])))) for e in PTS if e.get('tags', {}).get('railway') == 'station']
DRIVE = [r for r in S['roads'] if r['cls'] in ('major', 'minor') and not r['tunnel']]; dl = [LineString(r['pts']) for r in DRIVE]; dtree = STRtree(dl)
ent = []
for e in PTS:
    t = e.get('tags', {})
    if t.get('railway') != 'subway_entrance': continue
    p = Point(*map(float, tm5186(e['lon'], e['lat'])))
    if not BOARD.buffer(30).contains(p): continue
    st = min(stations, key=lambda s: s[1].distance(p)); ln = dl[dtree.nearest(p)]; s = ln.project(p); a, b_ = ln.interpolate(max(0, s - 2)), ln.interpolate(min(ln.length, s + 2))
    ent.append({'xy': [round(p.x, 2), round(p.y, 2)], 'ang': round(math.atan2(b_.y - a.y, b_.x - a.x), 3), 'station': st[0] if st[1].distance(p) < 450 else '', 'ref': t.get('ref', '')})
S['transit'] = {'entrances': ent, 'stations': [{'name': n, 'xy': [round(p.x, 2), round(p.y, 2)]} for n, p in stations if BOARD.contains(p)]}
print('entrances', len(ent), 'stations', sorted({s['name'] for s in S['transit']['stations']}))

# ---- 보행 광장(highway=pedestrian + area=yes) ----
pl = []
for e in L('roads'):
    t = e.get('tags', {})
    if t.get('highway') == 'pedestrian' and t.get('area') == 'yes' and (p := waypoly(e)) is not None and (r := rings(p, 0.15)): pl.append({'rings': r, 'name': t.get('name', ''), 'sport': ''})
S['areas']['plaza'] = pl; print('plazas', len(pl))

# ---- 선릉·정릉: 봉분(OSM historic=tomb 윤곽)과 그 앞 정자각 방향, 홍살문 ----
jeong = {b['name']: np.array(b['rings'][0]).mean(0) for b in B if b['name'].endswith('정자각')}
S['tombs'] = []
for e in L('areas'):
    t = e.get('tags', {})
    if t.get('historic') != 'tomb' or not e.get('geometry'): continue
    c = xy(e['geometry']).mean(0); j = min(jeong.values(), key=lambda q: np.hypot(*(q - c)))
    S['tombs'].append({'name': t.get('name', ''), 'c': np.round(c, 2).tolist(), 'toward': np.round(j, 2).tolist()})
S['gates'] = []
for e in PTS:
    t = e.get('tags', {})
    if '홍살문' in t.get('name', ''):
        p = np.array(tm5186(e['lon'], e['lat']), float); j = min(jeong.values(), key=lambda q: np.hypot(*(q - p)))
        S['gates'].append({'name': t['name'], 'xy': np.round(p, 2).tolist(), 'ang': round(math.atan2(j[1] - p[1], j[0] - p[0]), 3)})
print('tombs', [t['name'] for t in S['tombs']], 'gates', len(S['gates']))

# ---- 교량: 짧은 것·보행로는 지면 도로로, 나머지는 끝점에서 7 m 까지 오르는 높이(nz)를 준다. 교량을 목록 끝으로 옮겨 건물 ID(10000+i)와 교량 ID(20000+ri)가 겹치지 않게 한다 ----
terms = np.array(S['bridge_terms']) if S['bridge_terms'] else np.zeros((0, 2))
for r in S['roads']:
    if not r['bridge']: continue
    ln = LineString(r['pts'])
    if ln.length < 60 or r['cls'] in ('foot', 'minor') or not ln.intersects(REG): r['bridge'] = False; continue
    r['nz'] = [round(float(min(7.0, 0.07 * np.hypot(*(terms - p).T).min())) if len(terms) else 7.0, 2) for p in np.array(r['pts'])]
S['roads'].sort(key=lambda r: r['bridge'])   # 안정 정렬: 교량만 뒤로
nb = [i for i, r in enumerate(S['roads']) if r['bridge']]
assert not nb or 10000 + len(B) <= 20000 + nb[0], '건물 ID 와 교량 ID 가 겹친다'
assert 20000 + len(S['roads']) < 30000
print('bridges kept', len(nb))

# ---- 삼성역 광장(무역센터 동남쪽 모퉁이: 코엑스 동측 광장 + 밀레니엄 광장 + 5·6번 출구 앞 공사 야적장) ----
# OSM 에는 이 블록이 상업 부지 한 덩어리로만 있어 빈 바닥으로 나온다. 윤곽은 네이버 지도 위성 사진(2026-11 열람)을 장면 좌표에 맞춰 놓고 눈으로 따 왔고(오차 2–3 m),
# 높이·색·시설 종류는 거리뷰(2026-07 촬영분)를 보고 정했다. 사진은 저장소에 넣지 않았다. 세우는 쪽은 plaza_samseong.py.
# 좌표계: 영동대로 남행 차로 중심선 위의 점 Q0 에서 북북서(NV)로 s, 그 왼쪽(서쪽, −EV)으로 d 만큼 = rd(s, d).
Q0, NV = np.array([1274.0, 464.0]), np.array([-260.0, 620.0]) / math.hypot(260.0, 620.0); EV = np.array([NV[1], -NV[0]])
def rd(s, d): return (Q0 + NV * s - EV * d).tolist()
def rrect(c, hl, hw, ax=NV):   # 축 ax 방향 반길이 hl, 반폭 hw 인 네모
    c, ax = np.array(c, float), np.array(ax, float); n_ = np.array([-ax[1], ax[0]]); return Polygon([c + ax * u * hl + n_ * v * hw for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
def ell(c, a, b, n=48, ax=(1.0, 0.0)):
    ax = np.array(ax, float); n_ = np.array([-ax[1], ax[0]]); return Polygon([np.array(c) + ax * a * math.cos(2 * math.pi * k / n) + n_ * b * math.sin(2 * math.pi * k / n) for k in range(n)])
def band(pts, w): return LineString(pts).buffer(w / 2, cap_style=2, join_style=1)
EDGE = 9.3                                                             # 차로 중심선에서 광장 가장자리까지(차로 반폭 + 보도 띠)
FENCE = [(1150.0, 470.1), (1214.5, 494.5), (1229.0, 546.0)]            # 광장과 야적장 사이 가림벽 선(서 → 동 → 북)
TH_N = [(1150.0, 444.8), (1181.0, 453.8), (1256.3, 482.1)]             # 테헤란로 북쪽 보도 끝선
gates = unary_union([Point(*e['xy']).buffer(5.5) for e in S['transit']['entrances'] if e['station'] == '삼성'])
yard = Polygon(FENCE + [rd(92.0, EDGE), rd(23.6, EDGE)] + TH_N[::-1]).buffer(0).difference(gates).buffer(-.01)
yard = max(yard.geoms, key=lambda g: g.area) if yard.geom_type == 'MultiPolygon' else yard
court = dict(c=[1189.5, 519.5], a=15.5, b=12.5)                        # 밀레니엄 광장의 원형 광장(지면 높이: 가운데 스테인리스 구, 둘레 강철 기둥). 위성 사진에서는 비스듬히 찍혀 타원으로 보인다
def esec(f0, f1, a0, a1, fa=None, fb=None, n=4.0):   # 원형 광장 둘레의 고리 조각(각도 a0–a1°, 반지름 비 f0–f1; fa·fb 를 주면 바깥 반지름을 m 로)
    A_ = np.radians(np.arange(a0, a1 + .01, n)); cx, cy = court['c']; ao, bo = (fa, fb) if fa else (court['a'] * f1, court['b'] * f1)
    return Polygon([(cx + ao * math.cos(t), cy + bo * math.sin(t)) for t in A_] + [(cx + court['a'] * f0 * math.cos(t), cy + court['b'] * f0 * math.sin(t)) for t in A_[::-1]])
stair = esec(1.1, None, 95.0, 235.0, 20.0, 19.5)                         # 광장 서북쪽을 감싸는 초승달꼴 내리막 계단(지하 상가 입구, 흰 난간벽). 실제 깊이 약 5 m 는 1.4 m 로 줄인다(지면 판이 −1.8 m 에 있고, 굽기가 −1.55 m 아래 지면을 물로 읽는다)
lawn = {  # 이름 → 꼴. 잔디(지면 분류)로 칠하고, 빌더가 낮은 돌 턱을 두른다
    'strip': Polygon([rd(96, EDGE + .3), rd(214, EDGE + .3), rd(214, EDGE + 4.5), rd(96, EDGE + 4.5)]),      # 길가 잔디 띠(가로수 줄)
    'p1': rrect((1199.0, 608.0), 5.0, 1.8), 'p2': rrect((1205.2, 584.5), 4.8, 2.2), 'p3': rrect((1216.5, 559.0), 5.0, 2.4),
    'hedge': band([(1167.5, 607.0), (1174.0, 590.0), (1180.0, 574.0), (1186.0, 556.0), (1188.5, 548.5)], 5.0),   # 아티움 앞 화단 띠
    'isle': ell((1142.0, 489.5), 5.2, 5.2), 'pl1': rrect((1162.0, 534.5), 1.6, 1.6, (1, 0)), 'pl2': rrect((1165.5, 525.0), 1.6, 1.6, (1, 0)),
    'egg': ell((1202.0, 497.0), 2.2, 2.2, 16),
    'rim_e': esec(1.05, 1.24, -22.0, 22.0), 'rim_n': esec(1.05, 1.24, 68.0, 92.0), 'rim_s': esec(1.05, 1.24, 238.0, 292.0)}   # 원형 광장 돌 턱 바깥의 잔디 띠
for k in range(6): lawn['t%d' % k] = rrect(np.array([1187.0, 583.0]) + NV * k * 2.7 + EV * ((k % 2) * 2.4 - 1.2), 1.15, .9)   # 디딤 잔디(엇갈린 작은 네모)
bed = {  # 꽃밭(붉은·분홍 꽃). 지면 분류는 잔디, 빌더가 돌 턱 + 꽃 덩어리를 올린다
    'garden': Polygon([(1163.0, 631.0), (1182.0, 632.0), (1175.0, 660.0), (1166.0, 660.0), (1160.0, 648.0)]),
    'oval1': ell((1151.0, 669.0), 7.0, 4.6, 24, NV), 'oval2': ell((1144.0, 685.0), 7.0, 4.6, 24, NV),
    'wave': band([(1171.5, 596.0), (1176.5, 586.0), (1179.5, 575.0), (1184.5, 566.0), (1186.0, 556.0)], 1.8)}
green = unary_union(list(lawn.values()) + list(bed.values()))
green = green.difference(stair)
pave = Polygon([(1118.0, 457.2)] + FENCE + [rd(92.0, EDGE), rd(259.8, EDGE), (1128.0, 700.0), (1128.0, 600.0), (1118.0, 560.0)]).buffer(0).difference(yard.buffer(.01))
for g_, key, nm in [(pave.difference(green), 'plaza', '코엑스 동측 광장'), (green.intersection(pave), 'grass', '코엑스 동측 광장 화단'), (yard, 'dirt', '삼성역 광장 공사 야적장')]:
    for q in (g_.geoms if hasattr(g_, 'geoms') else [g_]):
        if q.geom_type == 'Polygon' and q.area > 2: S['areas'].setdefault(key, []).append({'rings': [np.round(np.array(r.coords), 2).tolist() for r in [q.exterior] + list(q.interiors)], 'name': nm, 'sport': ''})
R2 = lambda g: np.round(np.array(g.exterior.coords), 2).tolist()
S['samseong'] = {
    'q0': Q0.tolist(), 'nv': NV.tolist(), 'edge': EDGE, 'fence': FENCE, 'yard': R2(yard), 'court': court, 'stair': dict(a0=95.0, a1=235.0, f=1.1, a=20.0, b=19.5),
    'pave': [np.round(np.array(r.coords), 2).tolist() for r in [pave.exterior] + list(pave.interiors)],
    'lawn': {k: R2(v) for k, v in lawn.items()}, 'bed': {k: R2(v) for k, v in bed.items()},
    'egg': dict(c=[1190.0, 496.5], h=18.0, r=3.4),                                                    # 달걀꼴 은회색 조형탑(꼭대기에 금속 고리)
    'pavs': [dict(c=[1175.7, 601.0], hl=4.5, hw=2.0), dict(c=[1186.7, 575.5], hl=4.0, hw=2.0), dict(c=[1197.0, 553.5], hl=3.5, hw=2.0)],   # 얕은 못 가운데 선 줄무늬 파빌리온(지하 상가 환기·채광 시설)
    'canopy': dict(c=[1171.5, 537.5], ax=[.55, -.83], hl=4.5, hw=2.4),                                # 지하 상가로 내려가는 에스컬레이터 덮개(파란 유리)
    'dome': dict(c=[1141.5, 517.5], r=4.6), 'flags': [[1119.0 + 1.9 * k, 474.0 + .75 * k] for k in range(8)], 'stone': [1181.0, 492.5],   # 호텔 앞 유리 원형 지붕과 깃대 줄, 돌 조형 기둥
}
# 광장 나무: 목록 끝에 붙인다(나무 모양은 목록 순번으로 정해지므로, 중간에 끼우거나 빼면 지도 전체의 나무가 달라진다)
_new = [(1162.0, 534.5, 2.2), (1165.5, 525.0, 2.2), (1202.0, 497.0, 2.6), (1171.0, 598.5, 2.3), (1176.5, 582.5, 2.4), (1182.5, 566.0, 2.3), (1187.5, 552.0, 2.2)] + \
       [(1142.0 + 2.9 * math.cos(a), 489.5 + 2.9 * math.sin(a), 2.7) for a in (0.4, 2.5, 4.6)]
S['trees'] += [[x, y, r, 0] for x, y, r in _new]
print('samseong plaza: pave', round(pave.area), 'yard', round(yard.area), 'green', round(green.area), 'trees +', len(_new))

# ---- 아파트 단지: 동을 단지(landuse=residential 면)로 묶고, 단지 마당(정원·지상 주차장·둘레 화단)과 나무, 출입구 자리를 더한다 ----
# 거리뷰(2018–2026 촬영분, 단지 26곳의 정문 앞)와 위성 사진(옛 단지 4곳)에서 본 것: 2000년대 이후 단지(도곡렉슬·힐스테이트·래미안·e편한세상)는 지상이 정원이고 차는 지하로 들어간다. 1970–80년대 단지(은마·개포우성)는 동 앞이 지상 주차장이고
# 둘레와 동 옆에 큰 나무가 줄지어 있다. 단지의 연대는 층수 중앙값으로 가른다(15층 이하 = 옛 단지, 추정). 마당 배치(화단 폭, 주차 띠 자리)는 규칙으로 만든 것이라 실제 조경과 다르다.
import re, shapely
B = S['buildings']; APTK = ('apartments', 'residential', 'dormitory', 'officetel')
bpoly = [Polygon(b['rings'][0]).buffer(0) for b in B]; btree = STRtree(bpoly)
DRV = [(LineString(r['pts']), r) for r in S['roads'] if r['cls'] in ('major', 'minor') and not r['tunnel'] and not r['bridge']]; drt = STRtree([l for l, _ in DRV])
MAJ = [(l, r) for l, r in DRV if r['cls'] == 'major']; mjt = STRtree([l for l, _ in MAJ])
for b, bp in zip(B, bpoly):   # 건물이 면한 길(12 m 안): 큰길가는 상가·사무실, 이면도로는 빌라·주택으로 꾸민다(lm_build 의 detail.py)
    k = drt.nearest(bp); b['rd'] = ('major' if any(MAJ[j][0].distance(bp) - MAJ[j][1]['w'] / 2 < 14 for j in mjt.query(bp.buffer(34))) else DRV[k][1]['cls'] if DRV[k][0].distance(bp) - DRV[k][1]['w'] / 2 < 12 else '')   # 큰길이 14 m 안이면 큰길가(가장 가까운 길이 뒤쪽 진입로여도)
    m = re.search(r'(\d{1,4}|[A-Z])\s*동?$', b['name']); b['no'] = m.group(1) if m else ''
res = [(Polygon(a['rings'][0], a['rings'][1:]).buffer(0), a['name']) for a in S['areas'].get('resi_land', [])]; rtree = STRtree([q for q, _ in res]) if res else None; grp = {}
for b, bp in zip(B, bpoly):
    if b['kind'] not in APTK or b['lv'] < 6 or rtree is None: continue
    pt = bp.representative_point()
    for k in rtree.query(pt):
        if res[k][0].contains(pt): grp.setdefault(int(k), []).append(b); break
roadsurf = unary_union([l.buffer(r['w'] / 2 + .8, cap_style=2) for l, r in DRV]); footsurf = unary_union([LineString(r['pts']).buffer(r['w'] / 2 + .3, cap_style=2) for r in S['roads'] if r['cls'] == 'foot' and not r['tunnel']] + [Point(0, 0).buffer(.01)])
hard = unary_union([Polygon(a['rings'][0]).buffer(0) for k in ('pitch', 'play', 'parking', 'pond', 'plaza') for a in S['areas'].get(k, [])] + [Point(0, 0).buffer(.01)])
def _add(key, g, nm):
    for q in (g.geoms if hasattr(g, 'geoms') else [g]):
        if q.geom_type == 'Polygon' and q.area > 12 and (r_ := rings(q, .2)): S['areas'].setdefault(key, []).append({'rings': r_, 'name': nm, 'sport': ''})
S['complexes'] = []; tkey = {(round(t[0] / 2.0), round(t[1] / 2.0)) for t in S['trees']}; nt0 = len(S['trees'])
for k, bs in sorted(grp.items()):
    p, nm = res[k]
    if len(bs) < 3 or not p.intersects(BOARD.buffer(60)): continue
    lv = float(np.median([b['lv'] for b in bs])); era = 'old' if lv <= 15 else 'new'; ci = len(S['complexes']); seed = zlib.crc32((nm or str(k)).encode()) % 100000
    for b in bs: b['cx'] = ci
    ins = [bpoly[j] for j in btree.query(p) if bpoly[j].intersects(p)]; apron = unary_union([q.buffer(2.6 if era == 'new' else 1.6, join_style=2) for q in ins])
    yard = p.buffer(-1.2).difference(roadsurf).difference(hard)
    if era == 'new': green = yard.difference(apron); lots = None                     # 지상은 정원(동 둘레 2.6 m 만 포장)
    else:
        strips = []                                                                    # 동 남쪽 앞의 주차 띠(두 줄 주차 + 통로 = 폭 17 m)
        for b in bs:
            q = Polygon(b['rings'][0]); mc = np.array(q.minimum_rotated_rectangle.exterior.coords); e0, e1 = mc[1] - mc[0], mc[2] - mc[1]
            if np.hypot(*e0) < np.hypot(*e1): e0, e1 = e1, e0
            Lx_, Ly_ = np.hypot(*e0), np.hypot(*e1); ax = e0 / Lx_; nv = np.array([-ax[1], ax[0]]); nv = nv if nv[1] < 0 else -nv
            for sg, hw in ((1, 8.5), (-1, 5.5)):   # 남쪽은 두 줄 주차 + 통로(17 m), 북쪽(복도·출입구 쪽)은 한 줄 + 통로(11 m) — 위성 사진의 은마·개포우성·역삼럭키·서초진흥
                c = np.array(q.centroid.coords[0]) + nv * sg * (Ly_ / 2 + 3.0 + hw); strips.append(Polygon([tuple(c + ax * su * (Lx_ / 2 - 1) + nv * sv * hw) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]))
        lots = []; used = apron
        for st in strips:
            g = st.intersection(yard).difference(used)
            g = max(g.geoms, key=lambda q: q.area) if hasattr(g, 'geoms') and len(g.geoms) else g
            if g.geom_type == 'Polygon' and g.area > 300: lots.append(g); used = used.union(g.buffer(1.0))
        green = yard.difference(p.buffer(-6.0)).union(unary_union([q.buffer(5.0, join_style=2) for q in ins]).intersection(yard)).difference(apron).difference(unary_union(lots + [Point(0, 0).buffer(.01)]).buffer(.5))   # 둘레 화단 띠 + 동 둘레 화단
        for g in lots: _add('parking', g, nm + ' 주차장')
    green = green.buffer(-.4).buffer(.4); _add('grass', green, nm + ' 정원')
    if not green.is_empty:   # 조경수: 정원에 촘촘히(옛 단지는 큰 나무)
        x0, y0, x1, y1 = green.bounds; n = int(green.area / (40 if era == 'new' else 34)); rg = np.random.default_rng(seed); xs, ys = rg.uniform(x0, x1, n * 3), rg.uniform(y0, y1, n * 3)
        ok = shapely.contains_xy(green.buffer(-1.2), xs, ys) & ~shapely.contains_xy(footsurf, xs, ys)
        for x, y, rr in zip(xs[ok][:n], ys[ok][:n], rg.uniform(2.3, 3.6 if era == 'new' else 4.4, int(ok.sum()))[:n]):
            kk = (round(x / 2.0), round(y / 2.0))
            if kk not in tkey: tkey.add(kk); S['trees'].append([round(float(x), 2), round(float(y), 2), round(float(rr), 2), 0])
    gates = []   # 차도가 단지 경계를 넘는 자리: 담을 끊고, 넓은 길 둘에는 문주를 세운다
    ring_ = p.buffer(-.8).exterior if p.buffer(-.8).geom_type == 'Polygon' else p.exterior
    for j in drt.query(ring_):
        l, r = DRV[j]; x_ = l.intersection(ring_)
        for q in ([x_] if x_.geom_type == 'Point' else [g for g in getattr(x_, 'geoms', []) if g.geom_type == 'Point']):
            s_ = l.project(q); a_, b_ = l.interpolate(max(0, s_ - 2)), l.interpolate(min(l.length, s_ + 2)); gates.append([round(q.x, 2), round(q.y, 2), round(math.atan2(b_.y - a_.y, b_.x - a_.x), 3), r['w'], 0])
    for g in sorted(gates, key=lambda g: -g[3])[:2]: g[4] = 1
    S['complexes'].append({'name': nm, 'rings': rings(p, .3), 'era': era, 'seed': seed, 'lv': lv, 'n': len(bs), 'gates': gates})
# ---- 주택가: 거리뷰에서 본 동네별 외장 경향, 단독주택의 마당(담·정원수) ----
# 2026-11-13 에 본 골목 19곳(경도, 위도, 경향). brick = 붉은·고동색 벽돌 다세대가 대부분, new = 흰 석재 판·짙은 타일·송판 노출 콘크리트의 새 다세대, house = 박공지붕 벽돌 단독주택과 담장·정원수,
# shop = 학원·가게가 든 근린 건물, mixed = 섞임. 본 자리에서 380 m 안의 건물이 그 경향을 따르고, 그 밖은 섞인 기본값이다(건물 하나하나를 맞춘 것이 아니다).
NBH = [(127.04386, 37.49603, 'new'), (127.05326, 37.49874, 'shop'), (127.05341, 37.5173, 'house'), (127.02945, 37.51027, 'mixed'), (127.04457, 37.51277, 'mixed'), (127.0442, 37.50566, 'brick'), (127.03523, 37.49626, 'brick'),
       (127.06174, 37.51745, 'house'), (127.05274, 37.51046, 'brick'), (127.02955, 37.5033, 'house'), (127.04424, 37.52228, 'brick'), (127.05853, 37.50082, 'brick'), (127.03846, 37.50347, 'new'), (127.03891, 37.51979, 'mixed'),
       (127.0385, 37.4965, 'shop'), (127.0330, 37.5090, 'shop'), (127.0500, 37.5140, 'brick'), (127.0570, 37.5020, 'mixed'), (127.0445, 37.5025, 'shop')]
nbxy = np.array([tm5186(lo, la) for lo, la, _ in NBH], float); nyard = 0; ntr = len(S['trees'])
# 건물별 지붕 종류(roof_classes.py 가 위성 화면에서 읽은 표. 없으면 지붕은 고정 난수): green 초록 방수 바닥, grey·light·dark 콘크리트·밝은·짙은 바닥, tile 붉은 기와, blue 파란 지붕, tan 황토색
RC = json.load(open('osm/roof_classes.json')) if os.path.exists('osm/roof_classes.json') else {}
for b in B: b['rf'] = RC.get(b['osm'], '')
if RC:   # 나무·그림자에 가려 읽지 못한 20 m 이하 건물: 45 m 안에서 가장 가까운 판독 건물의 종류를 따른다(같은 골목의 지붕은 대체로 비슷하다)
    from scipy.spatial import cKDTree
    kn = [i for i, b in enumerate(B) if b['rf']]; kt = cKDTree(np.array([bpoly[i].centroid.coords[0] for i in kn])); nfill = 0
    for i, b in enumerate(B):
        if b['rf'] or b['h'] > 20: continue
        d_, j_ = kt.query(bpoly[i].centroid.coords[0])
        if d_ < 45: b['rf'] = B[kn[j_]]['rf'] if B[kn[j_]]['rf'] != 'blue' else 'grey'; b['rf_from'] = 'neighbour'; nfill += 1
    print('roof kinds filled from neighbours', nfill)
print('roof classes', sum(1 for b in B if b['rf']), 'of', len(B))
for i, (b, bp) in enumerate(zip(B, bpoly)):
    c = bp.centroid; d = np.hypot(nbxy[:, 0] - c.x, nbxy[:, 1] - c.y); j = int(d.argmin()); b['nb'] = NBH[j][2] if d[j] < 380 else ''
    rr = random.Random(b['seed'] * 7 + 3); nfl = max(1, round(max(3.0, b['h']) / 3.3)); hs = b['nb'] == 'house'
    b['house'] = bool(b['kind'] in ('house', 'detached') or (b['kind'] in ('yes', 'residential') and b['rd'] != 'major' and b['area'] < (170 if hs else 120) and nfl <= 2 and rr.random() < (.8 if hs else .5)))
    if not b['house'] or b['area'] < 40: continue
    lot = bp.buffer(2.6, join_style=2).difference(unary_union([bpoly[k].buffer(.5) for k in btree.query(bp.buffer(3.2)) if k != i] + [Point(0, 0).buffer(.01)])).difference(roadsurf)
    lot = next((q for q in (lot.geoms if hasattr(lot, 'geoms') else [lot]) if q.geom_type == 'Polygon' and q.buffer(.1).contains(bp.representative_point())), None)
    if lot is None or lot.area < bp.area * 1.3 or lot.interiors: continue
    b['yard'] = rings(lot, .2); nyard += 1; gdn = lot.buffer(-.9).difference(bp.buffer(1.1))   # 담 안 마당의 정원수 한두 그루
    for _ in range(rr.choice([1, 1, 2])):
        if gdn.is_empty: break
        x0, y0, x1, y1 = gdn.bounds
        for _t in range(12):
            q = Point(rr.uniform(x0, x1), rr.uniform(y0, y1)); kk = (round(q.x / 2.0), round(q.y / 2.0))
            if gdn.contains(q) and kk not in tkey: tkey.add(kk); S['trees'].append([round(q.x, 2), round(q.y, 2), round(rr.uniform(1.7, 2.5), 2), 0]); break
print('houses', sum(1 for b in B if b['house']), 'with yard', nyard, 'yard trees +', len(S['trees']) - ntr, 'frontage major', sum(1 for b in B if b['rd'] == 'major'))
print('complexes', len(S['complexes']), 'old', sum(c['era'] == 'old' for c in S['complexes']), 'apartments in complexes', sum(1 for b in B if 'cx' in b), 'garden trees +', len(S['trees']) - nt0)

S['extra'] = 'teheran/prep_extra.py'
json.dump(S, open('scene.json', 'w'), separators=(',', ':'))
print('wrote scene.json')
