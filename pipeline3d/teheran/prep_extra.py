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

S['extra'] = 'teheran/prep_extra.py'
json.dump(S, open('scene.json', 'w'), separators=(',', ':'))
print('wrote scene.json')
