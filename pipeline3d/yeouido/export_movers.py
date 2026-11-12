# [2차] 이동 스프라이트(열차·버스·배) 경로 자료. 정지 조건 렌더에는 굽지 않고, 앱이 경복궁 판의 차량처럼 실행 시 상자 모형으로 그려 움직인다(app/src/vehicles.js·movers.js 방식).
# 사용: ../gyeongbokgung/venv/bin/python export_movers.py  → movers/C_movers.json
# 좌표: scene.json 과 같은 지역 좌표(m, EPSG:5186 − org), z = 레일·노면·수면 높이(m). 판 C 카메라로 화면 투영은 cam.py Cam('C').proj.
import json, math, os, numpy as np
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import unary_union, linemerge
from cam import Cam
BOARD = os.environ.get('YD_BOARD', 'C')   # [5차] YD_BOARD=F → movers/F_movers.json
S = json.load(open('scene.json')); C = Cam(BOARD)
REG = Polygon([C.unproj(X, Y, 0)[:2] for X, Y in ((0, 0), (C.W, 0), (C.W, C.H), (0, C.H))]).buffer(150)
def P(r): return Polygon(r[0], r[1:]).buffer(0)
WATER = unary_union([P(w['rings']) for w in S['water']]); WL = -1.8
def zline(r):
    pts = np.array(r['pts'], float)
    if r['bridge'] and r.get('nz'): z = np.array(r['nz'], float)
    else: z = np.zeros(len(pts))
    return pts, z
def key(p): return '%.1f,%.1f' % (p[0], p[1])
out = {'about': '여의도 판 ' + BOARD + ' 이동 스프라이트 경로. 정지 렌더(조건 렌더)에는 열차·버스·배가 없다. 앱이 이 경로를 따라 실행 시 그린다.',
       'crs': 'scene.json 지역 좌표(m), z m', 'board': BOARD, 'rail_lanes': [], 'bus_lanes': [], 'boat_routes': [], 'specs': {}}
# 열차: 지상·교량 철도(경부선 = 1호선·간선 열차), 터널 구간은 hidden=true(신림선 등 지하 구간 — 화면에 그리지 않음)
for i, r in enumerate(S['roads']):
    if r['cls'] != 'rail': continue
    ln = LineString(r['pts'])
    if not ln.intersects(REG): continue
    pts, z = zline(r); z = z + 0.25  # 도상(자갈) 높이
    out['rail_lanes'].append({'id': len(out['rail_lanes']), 'road_idx': i, 'line': r['name'] or r['hw'], 'kind': r['hw'], 'hidden': bool(r['tunnel']), 'bridge': bool(r['bridge']),
                              'length': round(ln.length, 2), 'a': key(pts[0]), 'b': key(pts[-1]), 'pts': [[round(float(x), 2), round(float(y), 2), round(float(zz), 2)] for (x, y), zz in zip(pts, z)]})
# 버스: 간선·보조간선(양방향은 진행 방향 오른쪽 차로 중심으로 ±w/4 오프셋). 교량 구간은 상판 높이.
for i, r in enumerate(S['roads']):
    if r['cls'] != 'major' or r['tunnel'] or r['hw'] not in ('trunk', 'primary', 'secondary', 'tertiary', 'trunk_link', 'primary_link', 'secondary_link'): continue
    ln = LineString(r['pts'])
    if not ln.intersects(REG) or ln.length < 20: continue
    pts, z = zline(r); cum = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    dirs = [1] if r['oneway'] else [1, -1]
    for d in dirs:
        base = ln if d == 1 else LineString(pts[::-1])
        off = 0.0 if r['oneway'] else -r['w'] / 4   # 오른쪽 통행 → 진행 방향 오른쪽(음의 오프셋)
        try: g = base.offset_curve(off) if off else base
        except Exception: continue
        if g.geom_type != 'LineString' or g.length < 10: continue
        q = np.array(g.coords); s_ = np.array([ln.project(Point(*p)) for p in q]); zz = np.interp(s_, cum, z)
        out['bus_lanes'].append({'id': len(out['bus_lanes']), 'road_idx': i, 'name': r['name'], 'highway': r['hw'], 'dir': d, 'length': round(g.length, 2), 'a': key(q[0]), 'b': key(q[-1]),
                                 'pts': [[round(float(x), 2), round(float(y), 2), round(float(h) + 0.05, 2)] for (x, y), h in zip(q, zz)]})
# 배: 한강버스(여의도선착장 정차)와 유람선. OSM 에 항로가 없어 섬 북쪽 물가에서 띄운 선으로 만든다(추정).
isl = Polygon(json.load(open('island.json'))[0])
riv = max([g for g in getattr(WATER, 'geoms', [WATER])], key=lambda g: g.area)
def river_line(d):
    ring = isl.buffer(d, join_style=1).exterior.intersection(riv.buffer(-40)).intersection(REG)
    segs = [g for g in getattr(ring, 'geoms', [ring]) if g.geom_type == 'LineString']
    return max(segs, key=lambda g: g.length) if segs else None
stops = [s for s in S.get('transit', {}).get('stations', []) if '선착장' in s['name']]
for nm, d, kind, loop in (('한강버스(상·하행, 여의도선착장 정차)', 230.0, 'river_bus', False), ('유람선 순환(이랜드크루즈 선착장 발착, 추정)', 420.0, 'cruise', True)):
    g = river_line(d)
    if g is None: continue
    q = np.array(g.coords); q = q[::max(1, len(q) // 200)]
    route = {'id': len(out['boat_routes']), 'name': nm, 'kind': kind, 'loop': loop, 'length': round(LineString(q).length, 2), 'pts': [[round(float(x), 2), round(float(y), 2), WL] for x, y in q]}
    if kind == 'river_bus' and stops:
        sp = Point(*stops[0]['xy']); route['stops'] = [{'name': stops[0]['name'], 'xy': stops[0]['xy'], 's': round(LineString(q).project(sp), 2), 'dwell_s': 60}]
    out['boat_routes'].append(route)
# 상자 모형 규격(app/src/vehicles.js 의 parts 형식과 같은 생각: 길이·폭·높이 m + 색). 색·편성은 추정.
out['specs'] = {
    'metro_car': {'len': 19.5, 'wid': 3.12, 'h': 3.8, 'cars': 10, 'body': '#e9ecef', 'band': '#2f5aa8', 'roof': '#b9bec2', 'note': '수도권 1호선 전동차(차체 치수는 일반 규격, 색 추정)'},
    'intercity_car': {'len': 20.0, 'wid': 3.0, 'h': 3.9, 'cars': 8, 'body': '#f2f2f0', 'band': '#3a6fb6', 'roof': '#9aa1a6', 'note': '경부선 간선 열차(KTX·ITX 등 구분 없음, 추정)'},
    'bus': {'len': 11.0, 'wid': 2.5, 'h': 3.2, 'colors': ['#3a7bd5', '#4caf50', '#e53935'], 'note': '경복궁 판 vehicle_specs 와 같은 치수, 서울 버스 색(간선 파랑·지선 초록·광역 빨강)'},
    'river_bus': {'len': 35.0, 'wid': 9.0, 'h': 4.5, 'body': '#f4f4f2', 'band': '#1f7bbf', 'speed_mps': 7.0, 'note': '한강버스(치수·색 추정)'},
    'cruise': {'len': 45.0, 'wid': 10.0, 'h': 7.0, 'body': '#ffffff', 'band': '#c43a2a', 'speed_mps': 4.0, 'note': '한강 유람선(치수·색 추정)'},
}
os.makedirs('movers', exist_ok=True); json.dump(out, open('movers/' + BOARD + '_movers.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print({k: len(v) for k, v in out.items() if isinstance(v, list)}, 'rail km', round(sum(l['length'] for l in out['rail_lanes'] if not l['hidden']) / 1000, 2), 'boat', [(b['name'], b['length']) for b in out['boat_routes']])
