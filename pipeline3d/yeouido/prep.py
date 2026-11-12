# OSM 원자료(osm/*.json) → 지역 좌표(m) 장면 자료 scene.json.  사용: ../gyeongbokgung/venv/bin/python prep.py
# 좌표: EPSG:5186(중부원점 TM) 에서 ORG 를 뺀 값. x=동, y=북. 원점은 63빌딩 근처.
import json, math, random, collections, zlib, os
import numpy as np
import shapely
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, box
from shapely.ops import unary_union, polygonize, linemerge
from shapely.strtree import STRtree

ORG = json.loads(os.environ.get('P3D_ORG', '[194700.0, 546700.0]'))   # 다른 지역: P3D_ORG='[x, y]'(EPSG:5186 m), 작업 폴더(osm/ 가 있는 곳)에서 실행
def tm5186(lon, lat):
    a, f = 6378137.0, 1 / 298.257222101; e2 = f * (2 - f); ep2 = e2 / (1 - e2); lat0, lon0 = np.radians(38.0), np.radians(127.0)
    def M(p): return a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * p - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * np.sin(2 * p) + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * np.sin(4 * p) - (35 * e2 ** 3 / 3072) * np.sin(6 * p))
    p, l = np.radians(lat), np.radians(lon); N_ = a / np.sqrt(1 - e2 * np.sin(p) ** 2); T = np.tan(p) ** 2; C = ep2 * np.cos(p) ** 2; A = (l - lon0) * np.cos(p)
    x = N_ * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120) + 200000.0
    y = (M(p) - M(lat0) + N_ * np.tan(p) * (A ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24 + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720)) + 600000.0
    return x - ORG[0], y - ORG[1]
def xy(g):
    lon = np.array([q['lon'] for q in g]); lat = np.array([q['lat'] for q in g]); x, y = tm5186(lon, lat)
    return np.stack([x, y], 1)
def L(name): return json.load(open(f'osm/{name}.json'))['elements']
def num(s):
    try: return float(str(s).replace('m', '').strip())
    except Exception: return None

def relpoly(e):
    """멀티폴리곤 관계 → shapely (outer 합 − inner 합)."""
    out, inn = [], []
    for m in e.get('members', []):
        g = m.get('geometry')
        if not g or len(g) < 2: continue
        (inn if m.get('role') == 'inner' else out).append(LineString(xy(g)))
    def polys(ls):
        if not ls: return None
        pp = list(polygonize(unary_union(ls)))
        return unary_union([p.buffer(0) for p in pp]) if pp else None
    o, i = polys(out), polys(inn)
    if o is None: return None
    return o.difference(i) if i is not None else o
def waypoly(e):
    g = e.get('geometry')
    if not g or len(g) < 4 or g[0] != g[-1]: return None
    p = Polygon(xy(g)).buffer(0)
    return p if (not p.is_empty and p.area > 0.5) else None
def parts(g):
    if g is None or g.is_empty: return []
    if g.geom_type == 'Polygon': return [g]
    return [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon' and p.area > 0.5]
def rings(p, tol=0.05):
    p = p.simplify(tol)
    if p.geom_type != 'Polygon' or p.is_empty: return None
    return [np.round(np.array(r.coords), 2).tolist() for r in [p.exterior] + list(p.interiors)]

# ---------------- 건물 ----------------
stat = collections.Counter(); blds = []
seen_rel_ways = set()
raw = [e for e in L('buildings') if e['type'] == 'way'] + L('rel_buildings')
for e in raw:
    t = e.get('tags', {})
    if 'building' not in t and 'building:part' not in t: continue
    g = relpoly(e) if e['type'] == 'relation' else waypoly(e)
    for p in parts(g):
        if p.area < 6: continue
        blds.append({'osm': f"{e['type'][0]}{e['id']}", 'poly': p, 't': t, 'part': 'building' not in t or t.get('building') == 'no'})
# building:part 가 있는 윤곽은 파트로 대신한다(파트가 윤곽 면적의 절반 이상을 덮을 때)
pp_ = [b for b in blds if b['part'] and (num(b['t'].get('min_height')) or 0) < 3 and not num(b['t'].get('building:min_level'))]  # 지상에서 시작하는 파트만 윤곽을 대신한다(63스퀘어 같은 옥상 파트는 아님)
for b in blds:
    if b['part'] and b not in pp_: b['dropme'] = True  # 공중 파트는 버린다(랜드마크는 전용 모델)
tree = STRtree([b['poly'] for b in pp_]) if pp_ else None
drop = set()
for i, b in enumerate(blds):
    if b['part'] or tree is None: continue
    cov = [pp_[k] for k in tree.query(b['poly']) if pp_[k]['poly'].intersection(b['poly']).area > 0.6 * pp_[k]['poly'].area]
    if cov and unary_union([c['poly'] for c in cov]).intersection(b['poly']).area > 0.5 * b['poly'].area: drop.add(i); stat['outline_replaced_by_parts'] += 1
    else:
        for c in cov: c['dropme'] = True  # 덮는 비율이 낮은 파트는 버리고 윤곽을 쓴다
blds = [b for i, b in enumerate(blds) if i not in drop and not b.get('dropme')]

APT = ('apartments', 'residential', 'dormitory', 'officetel')
def est_height(t, area, rnd):
    """높이 태그가 없을 때의 추정(유형·면적). 반환 (h, 층수, 근거)."""
    k = t.get('building', 'yes')
    if k in ('roof', 'carport', 'shed', 'garage', 'kiosk', 'hut', 'toilets'): return 4.0, 1, 'est_type'
    if k in ('apartments', 'dormitory'): fl = 15 if area > 350 else rnd.choice([4, 5, 5])
    elif k == 'officetel': fl = 15 if area > 400 else 8
    elif k in ('office', 'commercial', 'retail', 'hotel'): fl = (rnd.choice([3, 4, 5]) if area > 4000 else rnd.choice([10, 12, 15]) if area > 1200 else rnd.choice([5, 6, 8]) if area > 400 else rnd.choice([3, 4, 5]))
    elif k in ('school', 'university', 'kindergarten', 'college'): fl = rnd.choice([3, 4, 5]) if area > 300 else 2
    elif k in ('church', 'cathedral', 'temple'): fl = 4 if area > 400 else 2
    elif k in ('house', 'detached'): fl = rnd.choice([1, 2, 2])
    elif k in ('industrial', 'warehouse'): fl = 2
    else: fl = (rnd.choice([1, 2, 2, 3]) if area < 90 else rnd.choice([2, 3, 3, 4, 5]) if area < 300 else rnd.choice([4, 5, 6, 7]) if area < 1000 else rnd.choice([4, 6, 8]) if area < 3000 else rnd.choice([2, 3, 4]))  # 넓은 바닥(시장·창고·역사)은 낮게
    return fl * (3.0 if k in APT + ('house',) else 3.6), fl, 'est_type_area'
B = []
for b in blds:
    t = b['t']; p = b['poly']; rnd = random.Random(zlib.crc32(b['osm'].encode()))
    h, lv, mh = num(t.get('height')), num(t.get('building:levels')), num(t.get('min_height')) or 0.0
    if mh == 0 and num(t.get('building:min_level')): mh = num(t.get('building:min_level')) * 3.5
    if h and h > 1: src = 'height'; lv = lv or max(1, round(h / 3.6))
    elif lv and lv >= 1:
        k = t.get('building', 'yes'); src = 'levels'
        h = lv * (2.9 if k in APT else 4.0 if lv >= 20 else 3.6) + (1.0 if lv < 20 else 6.0)
    else: h, lv, src = est_height(t, p.area, rnd)
    if h <= mh: mh = 0.0
    stat['h_' + src] += 1
    r = rings(p)
    if not r: continue
    B.append({'osm': b['osm'], 'rings': r, 'h': round(h, 1), 'min_h': round(mh, 1), 'lv': int(lv), 'src': src, 'kind': t.get('building') or 'part', 'part': b['part'],
              'name': t.get('name', ''), 'name_en': t.get('name:en', ''), 'colour': t.get('building:colour', ''), 'area': round(p.area, 1), 'seed': zlib.crc32(b['osm'].encode()) % 100000})
print('buildings', len(B), dict(stat))
bpolys = [Polygon(b['rings'][0]).buffer(0) for b in B]
bunion = unary_union([p.buffer(1.2) for p in bpolys])

# ---------------- 수역·녹지·기타 면 ----------------
A = collections.defaultdict(list)
def cls_of(t):
    n, w, l, u, am, mm = (t.get(k) for k in ('natural', 'water', 'leisure', 'landuse', 'amenity', 'man_made'))
    if n == 'water' or t.get('waterway') in ('riverbank', 'dock', 'boatyard'): return 'pond' if w in ('pond', 'fountain', 'basin', 'reflecting_pool') else 'water'
    if n in ('wood', 'scrub', 'shrub') or u == 'forest': return 'wood'
    if n in ('grassland', 'heath', 'wetland') or u in ('grass', 'village_green', 'meadow', 'recreation_ground', 'flowerbed') or l in ('park', 'garden', 'nature_reserve'): return 'grass'
    if n in ('sand', 'beach', 'shingle'): return 'sand'
    if l == 'pitch': return 'pitch'
    if l in ('playground', 'track'): return 'play'
    if l == 'swimming_pool': return 'pond'
    if am == 'parking': return 'parking'
    if u in ('construction', 'brownfield'): return 'dirt'
    if u == 'railway': return 'rail_land'
    if u in ('residential',): return 'resi_land'
    if u in ('commercial', 'retail', 'office', 'education', 'religious', 'industrial'): return 'comm_land'
    if mm == 'pier': return 'pier'
    return None
relways = set()
for e in L('rel_areas'):
    t = e.get('tags', {}); c = cls_of(t)
    if not c: continue
    for p in parts(relpoly(e)): A[c].append((p, t.get('name', ''), t.get('sport', '')))
for e in L('areas'):
    if e['type'] != 'way': continue
    t = e.get('tags', {}); c = cls_of(t)
    if not c: continue
    p = waypoly(e)
    if p is None:
        if c == 'pier' and e.get('geometry') and len(e['geometry']) >= 2: A['pier'].append((LineString(xy(e['geometry'])).buffer(2.0, cap_style=2), '', ''))
        continue
    A[c].append((p, t.get('name', ''), t.get('sport', '')))
water = unary_union([p for p, _, _ in A['water']]).buffer(0)
shapely.prepare(water); nfl = 0
for b in B:  # 물 위(수상 선착장·식당) 건물: 높이 태그가 없으면 7 m 이하로
    c_ = Polygon(b['rings'][0]).centroid
    if water.contains(c_) and b['src'] not in ('height', 'levels'): b['h'] = min(b['h'], 7.0); b['lv'] = min(b['lv'], 2); b['src'] += '+on_water'; nfl += 1
print('on-water buildings capped', nfl)
print({k: len(v) for k, v in A.items()}, 'water area km2', round(water.area / 1e6, 3))
# 물줄기 선(샛강 등, 면이 없는 것)
streams = []
for e in L('areas'):
    t = e.get('tags', {})
    if e['type'] == 'way' and t.get('waterway') in ('stream', 'canal', 'drain') and e.get('geometry') and t.get('tunnel') is None:
        ln = LineString(xy(e['geometry']))
        if ln.length > 5: streams.append({'pts': np.round(np.array(ln.coords), 2).tolist(), 'w': 9.0 if t.get('name') == '샛강' else 3.0, 'name': t.get('name', '')})
rows = [LineString(xy(e['geometry'])) for e in L('areas') if e['type'] == 'way' and e.get('tags', {}).get('natural') == 'tree_row' and e.get('geometry')]

# ---------------- 도로·교량·철도 ----------------
DEFW = {'motorway': (3, 3.5), 'trunk': (3, 3.5), 'primary': (3, 3.3), 'secondary': (2, 3.2), 'tertiary': (2, 3.0), 'residential': (1, 5.5), 'unclassified': (1, 5.5), 'living_street': (1, 5.0),
        'service': (1, 3.8), 'busway': (1, 3.6), 'pedestrian': (1, 6.0), 'footway': (1, 2.2), 'path': (1, 1.6), 'cycleway': (1, 2.6), 'steps': (1, 2.2), 'track': (1, 2.5), 'corridor': (1, 0)}
roads = []; rstat = collections.Counter(); nodeuse = collections.defaultdict(lambda: [0, 0])  # 좌표 → [교량 수, 비교량 수]
for e in L('roads'):
    t = e.get('tags', {}); g = e.get('geometry')
    if not g or len(g) < 2: continue
    hw, rw = t.get('highway'), t.get('railway')
    if not hw and not rw: continue
    if hw in ('proposed', 'construction', 'corridor', 'elevator', 'platform', 'bus_stop', 'rest_area', 'services') or t.get('indoor') or t.get('area') == 'yes' and hw != 'pedestrian': continue
    if rw and rw not in ('rail', 'light_rail', 'subway'): continue
    tun = t.get('tunnel') not in (None, 'no') or t.get('covered') == 'yes' or (num(t.get('layer')) or 0) < 0
    if rw == 'subway' and t.get('bridge') in (None, 'no'): continue  # 지하 구간(태그 누락 포함)은 그리지 않는다
    br = t.get('bridge') not in (None, 'no')
    base = (hw or 'rail').replace('_link', ''); link = bool(hw and hw.endswith('_link'))
    if rw: w, lanes = (5.0 if not br else 5.5), 1; cls = 'rail'
    else:
        dl, lw = DEFW.get(base, (1, 4.0)); lanes = num(t.get('lanes'));
        if link: dl = 1
        if lanes is None: lanes = dl * (1 if t.get('oneway') in ('yes', '1') or base in ('footway', 'path', 'cycleway', 'steps', 'service', 'residential', 'pedestrian', 'living_street', 'unclassified', 'busway', 'track') else 2)
        lanes = int(max(1, min(lanes, 8))); w = num(t.get('width')) or (lanes * lw + (0.8 if lanes > 1 or link else 0)); w = min(w, 40)
        cls = 'foot' if base in ('footway', 'path', 'steps', 'pedestrian', 'track') else 'cycle' if base == 'cycleway' else 'minor' if base in ('service', 'residential', 'living_street', 'unclassified', 'busway') else 'major'
    pts = xy(g)
    for q in (g[0], g[-1]): nodeuse[(q['lat'], q['lon'])][0 if br else 1] += 1
    if not br:
        for q in g[1:-1]: nodeuse[(q['lat'], q['lon'])][1] += 0  # 중간 점은 연결로 치지 않는다
    roads.append({'pts': np.round(pts, 2).tolist(), 'hw': hw or rw, 'cls': cls, 'lanes': lanes, 'w': round(w, 1), 'bridge': br, 'tunnel': tun and not br, 'oneway': t.get('oneway') in ('yes', '1'),
                  'layer': int(num(t.get('layer')) or 0), 'name': t.get('name', ''), 'area': t.get('area') == 'yes'})
    rstat[cls + ('_bridge' if br else '_tunnel' if tun else '')] += 1
print('roads', len(roads), dict(rstat))
# 교량 끝점(교량 way 와 일반 way 가 만나는 점) → 여기서 상판 높이 0
terms = []
for (lat, lon), (nb, nn) in nodeuse.items():
    if nb and nn: x, y = tm5186(lon, lat); terms.append([round(float(x), 2), round(float(y), 2)])
print('bridge terminals', len(terms))
# 횡단보도(점) → 가장 가까운 차도의 방향·너비
drive = [r for r in roads if r['cls'] in ('major', 'minor') and not r['bridge'] and not r['tunnel']]
dl_ = [LineString(r['pts']) for r in drive]; dtree = STRtree(dl_)
cross = []
for e in L('points'):
    if e['tags'].get('highway') != 'crossing': continue
    x, y = tm5186(e['lon'], e['lat']); pt = Point(float(x), float(y)); k = dtree.nearest(pt)
    if dl_[k].distance(pt) > 1.0 or drive[k]['w'] < 5: continue
    s = dl_[k].project(pt); a_, b_ = dl_[k].interpolate(max(0, s - 1)), dl_[k].interpolate(min(dl_[k].length, s + 1))
    cross.append([round(pt.x, 2), round(pt.y, 2), round(math.atan2(b_.y - a_.y, b_.x - a_.x), 3), drive[k]['w']])
print('crossings', len(cross))

# ---------------- 나무 ----------------
rnd = random.Random(63); T = []  # x, y, r, 종류(0 일반, 1 가로수, 2 숲)
roadsurf = unary_union([LineString(r['pts']).buffer(r['w'] / 2 + 0.4, cap_style=2) for r in roads if not r['tunnel'] and r['cls'] in ('major', 'minor', 'rail', 'cycle')])
footsurf = unary_union([LineString(r['pts']).buffer(r['w'] / 2 + 0.3, cap_style=2) for r in roads if not r['tunnel'] and r['cls'] == 'foot'])
hard = unary_union([p for c in ('pitch', 'play', 'parking', 'pond', 'pier') for p, _, _ in A[c]] + [Point(0, 0).buffer(0.1)])
block = unary_union([bunion, water.buffer(2.0), roadsurf, hard]); shapely.prepare(block); shapely.prepare(footsurf)
def scatter(poly, dens, rmin, rmax, kind, seed, avoid_foot=True):
    x0, y0, x1, y1 = poly.bounds; n = int(poly.area * dens);
    if n < 1: n = 1 if random.Random(seed).random() < poly.area * dens else 0
    if n == 0: return
    rg = np.random.default_rng(seed); xs = rg.uniform(x0, x1, n * 3); ys = rg.uniform(y0, y1, n * 3)
    ok = shapely.contains_xy(poly, xs, ys) & ~shapely.contains_xy(block, xs, ys)
    if avoid_foot: ok &= ~shapely.contains_xy(footsurf, xs, ys)
    xs, ys = xs[ok][:n], ys[ok][:n]; rs = rg.uniform(rmin, rmax, len(xs))
    T.extend([[round(float(x), 2), round(float(y), 2), round(float(r), 2), kind] for x, y, r in zip(xs, ys, rs)])
for e in L('points'):
    if e['tags'].get('natural') == 'tree':
        x, y = tm5186(e['lon'], e['lat']); T.append([round(float(x), 2), round(float(y), 2), round(rnd.uniform(2.2, 3.4), 2), 0])
n_osm = len(T)
for ln in rows:
    for s in np.arange(2, ln.length, 7.0): p = ln.interpolate(float(s)); T.append([round(p.x, 2), round(p.y, 2), round(rnd.uniform(2.4, 3.4), 2), 1])
n_row = len(T) - n_osm
for i, (p, _, _) in enumerate(A['wood']): scatter(p, 1 / 34, 2.6, 4.4, 2, 1000 + i, False)
n_wood = len(T) - n_osm - n_row
woodu = unary_union([p for p, _, _ in A['wood']] + [Point(0, 0).buffer(0.1)])
for i, (p, _, _) in enumerate(A['grass']):
    q = p.difference(woodu)
    for g in parts(q): scatter(g, 1 / 150, 2.2, 3.8, 0, 5000 + i)
n_grass = len(T) - n_osm - n_row - n_wood
for i, (p, _, _) in enumerate(A['resi_land']): scatter(p, 1 / 170, 2.0, 3.4, 0, 9000 + i)
n_resi = len(T) - n_osm - n_row - n_wood - n_grass
# 가로수: 큰길·이면도로 양쪽
st0 = len(T)
for r in roads:
    if r['bridge'] or r['tunnel'] or r['hw'] not in ('primary', 'secondary', 'tertiary', 'residential') or r['w'] < 5: continue
    ln = LineString(r['pts'])
    if ln.length < 25: continue
    for side in (1, -1):
        try: off = ln.offset_curve(side * (r['w'] / 2 + (2.2 if r['cls'] == 'major' else 1.3)))
        except Exception: continue
        for g in ([off] if off.geom_type == 'LineString' else list(getattr(off, 'geoms', []))):
            if g.is_empty or g.length < 8: continue
            ss = np.arange(4.0, g.length - 3.0, 9.0 if r['cls'] == 'major' else 12.0); pts_ = shapely.line_interpolate_point(g, ss)
            xs, ys = shapely.get_x(pts_), shapely.get_y(pts_); ok = ~shapely.contains_xy(block, xs, ys)
            T.extend([[round(float(x), 2), round(float(y), 2), round(rnd.uniform(2.0, 3.0), 2), 1] for x, y in zip(xs[ok], ys[ok])])
# 너무 가까운 나무 솎기(격자 2 m)
seen = set(); T2 = []
for t in T:
    k = (round(t[0] / 2.0), round(t[1] / 2.0))
    if k in seen: continue
    seen.add(k); T2.append(t)
print('trees', len(T2), {'osm_node': n_osm, 'tree_row': n_row, 'wood': n_wood, 'grass': n_grass, 'resi': n_resi, 'street': len(T) - st0, 'thinned': len(T) - len(T2)})

def dump_polys(lst, tol=0.15):
    out = []
    for p, name, sport in lst:
        for g in parts(p):
            r = rings(g, tol)
            if r: out.append({'rings': r, 'name': name, 'sport': sport})
    return out
scene = {'org': ORG, 'crs': 'EPSG:5186 - org', 'buildings': B, 'roads': roads, 'bridge_terms': terms, 'cross': cross, 'streams': streams, 'trees': T2,
         'areas': {k: dump_polys(v) for k, v in A.items() if k != 'water'}, 'water': dump_polys([(g, '', '') for g in parts(water)], 0.3),
         'stats': {'buildings': dict(stat), 'roads': dict(rstat)}}
json.dump(scene, open('scene.json', 'w'), separators=(',', ':'))
print('wrote scene.json')

# ---------------- 랜드마크 윤곽(전용 모델·건물별 설정의 기준) ----------------
LM = {'63': ('w', 64989671), 'parc1': ('w', 874639189), 'parc2': ('w', 874639190), 'ifc1': ('w', 621752526), 'ifc2': ('w', 621752527), 'ifc3': ('w', 621752528),
      'conrad': ('w', 500362301), 'lg': ('r', 6033900), 'fki': ('w', 681805210), 'anchor': ('w', 1267509202), 'post': ('w', 681807943), 'assembly': ('w', 270596342)}
if os.environ.get('P3D_LM'): LM = {k: tuple(v) for k, v in json.loads(os.environ['P3D_LM']).items()}   # 다른 지역의 랜드마크 표: {"키": ["w"|"r", OSM id]}
els = {(e['type'][0], e['id']): e for e in L('buildings') + L('rel_buildings')}
scene['landmarks'] = {}
for k, key in LM.items():
    e = els.get(key)
    if not e: print('landmark missing', k); continue
    g = relpoly(e) if e['type'] == 'relation' else waypoly(e)
    scene['landmarks'][k] = {'osm': f'{key[0]}{key[1]}', 'rings': [rings(p, 0.02) for p in parts(g)], 'h': num(e['tags'].get('height')), 'lv': num(e['tags'].get('building:levels')), 'name': e['tags'].get('name', '')}
json.dump(scene, open('scene.json', 'w'), separators=(',', ':'))
print('landmarks', list(scene['landmarks']))
