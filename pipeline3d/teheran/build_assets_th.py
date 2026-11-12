#!/usr/bin/env python3
"""테헤란로 굽기: 조건 렌더(passT/)를 앱 자산(assets/teheran/)으로.
양식 패스(이미지 모델) 없이 조건 렌더를 그대로 그림으로 쓴다 = 여의도 굽기의 자리표시 경로(cache → quant → maps → tiles → mapjson, 잠금 없음).
단계 함수는 ../yeouido/build_assets_yd.py 의 것을 그대로 부르고, 판마다 다른 상수(그림 px, 깊이 단위)와 랜드마크 표만 바꾼다.

  python build_assets_th.py --pass passT --work bake [--raw 양식 결과.png] [--install ../../assets/teheran] [단계 ...]     (작업 폴더에서)
"""
import argparse, json, shutil, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'yeouido'))
import build_assets_yd as yd

# 지도에 이름을 붙일 곳: (키, 이름, 종류, 조건 렌더의 종류 이름들). 키는 src/maps.js 의 바로가기가 쓴다
LM_OBJ = [('wework', '위워크타워(선릉)', 'tower', ['landmark:wework']), ('trade', '트레이드타워', 'tower', ['landmark:trade']), ('asem', '아셈타워', 'tower', ['landmark:asem']),
          ('parnas', '파르나스타워', 'tower', ['landmark:parnas']), ('coex', '코엑스', 'landmark', ['landmark:coex']), ('gfc', '강남파이낸스센터', 'tower', ['landmark:gfc']),
          ('db', 'DB금융센터', 'tower', ['landmark:db']), ('posco', '포스코센터', 'tower', ['landmark:posco_e', 'landmark:posco_w']), ('gt', 'GT타워', 'tower', ['landmark:gt']),
          ('samsung', '삼성 서초사옥', 'tower', ['landmark:samsung_e', 'landmark:samsung_c', 'landmark:samsung_l']), ('centerfield', '센터필드', 'tower', ['landmark:cf_e', 'landmark:cf_w']),
          ('gs', 'GS타워', 'tower', ['landmark:gs']), ('meritz', '메리츠타워', 'tower', ['landmark:meritz']), ('glass', '글라스타워', 'tower', ['landmark:glass']),
          ('millennium', '코엑스 밀레니엄 광장', 'landmark', ['landmark:millennium'])]   # 삼성역 광장의 원형 광장(plaza_samseong.py)
LM_AREA = [('seolleung', '선릉과 정릉(선정릉)', [('grass', '삼릉공원 / 서울 선릉과 정릉')])]
STEPS = ['cache', 'quant', 'maps', 'tiles', 'mapjson']


def finish_mapjson(a):
    """여의도 map.json 틀에서 지도 이름·설명을 바꾸고, 왕릉(봉분) 자리를 더하고, 굽기 입력 경로를 뺀다."""
    f = Path(a.work) / 'map.json'
    m = json.loads(f.read_text()); S = json.load(open(a.scene)); cam = yd.Cam(yd.load_meta(a))
    cm = round(yd.PX * 100, 3)
    m.update(schema='map-json-1', id='teheran', name='테헤란로', name_en='Teheran-ro',
             board='T (θ=−24: 남남서쪽에서 북북동쪽을 봄. 강남역 왼쪽 아래, 선릉 가운데, 삼성역·코엑스 오른쪽 위)',
             note=f'canvas = {cm} cm 그림 px, map_px = depth_rg8·classes·crown 의 칸({yd.PX * yd.F} m). 경로의 pts = 장면 지역 좌표 m [x, y, z], px = 캔버스 px [X, Y](지도 px 는 ÷8).')
    m.pop('raw', None); m.pop('water_level_m', None)
    m['tiles']['note'] = f'z = 지도 칸 하나당 그림 px. z8 이 원본({cm} cm). 아래 단계는 양자화한 z8 의 BOX 축소'
    m['depth']['ground_note'] = '지면 0 m. 봉분 언덕은 지면 ID 의 실제 형상. 칸 최솟값'
    m['camera']['name'] = f'teheran_T_theta{int(cam.theta)}'; m['camera']['note'] = '정사투영, 카메라가 남남서쪽에서 북북동쪽을 본다(θ=−24), 고도 35°'
    short = {'선릉 성종왕릉': ('tomb_seongjong', '선릉(성종)'), '선릉 성종왕비정현왕후릉': ('tomb_jeonghyeon', '선릉(정현왕후)'), '삼릉공원 중종정릉': ('tomb_jungjong', '정릉(중종)')}
    for t in S.get('tombs', []):
        k, nm = short.get(t['name'], ('tomb_' + t['name'], t['name'])); p = cam.proj([t['c'] + [0.0]])[0] / yd.F
        m['landmarks'][k] = {'name': nm, 'kind': 'place', 'in_canvas': True, 'px': [round(float(p[0]), 1), round(float(p[1]), 1)], 'local_m': t['c'] + [0.0]}
    if m['landmarks'].get('seolleung', {}).get('px'): m['landmarks']['park'] = dict(m['landmarks']['seolleung'])   # 앱의 도시 사람 장면(벤치·산책·눈사람)이 'park' 앵커 둘레에 놓인다
    f.write_text(json.dumps(m, ensure_ascii=False, separators=(',', ':')))
    yd.log('map.json(teheran)', f.stat().st_size, 'B; landmarks', sorted(k for k, v in m['landmarks'].items() if v.get('px')), 'lanes', len(m['lanes']), 'walk', len(m['walk_paths']))


def install(a):
    W_, D = Path(a.work), Path(a.install)
    D.mkdir(parents=True, exist_ok=True)
    if (D / 'tiles').exists(): shutil.rmtree(D / 'tiles')
    shutil.copytree(W_ / 'tiles', D / 'tiles')
    for n in ('bg.png', 'bg_1x.png', 'depth_rg8.png', 'classes.png', 'crown.png', 'map.json'): shutil.copy(W_ / n, D / n)
    yd.log('installed', D, sum(1 for _ in (D / 'tiles').rglob('*.png')), 'tile files')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('steps', nargs='*', default=STEPS)
    ap.add_argument('--pass', dest='pass_dir', default='passT')
    ap.add_argument('--work', default='bake')
    ap.add_argument('--raw', help='양식 패스 결과(없으면 조건 렌더 cond.png 를 그대로 쓴다)')
    ap.add_argument('--scene', default='scene.json')
    ap.add_argument('--movers', default='movers/T_movers.json')
    ap.add_argument('--install', help='끝나면 자산을 복사해 둘 폴더(assets/teheran)')
    ap.add_argument('--colors', type=int, default=128)
    ap.add_argument('--jobs', type=int, default=12)
    a = ap.parse_args()
    a.placeholder = a.raw is None; a.raw = a.raw or str(Path(a.pass_dir) / 'cond.png')
    a.make_tiles = str(HERE.parent / 'gyeongbokgung' / 'make_tiles.py')
    meta = json.load(open(Path(a.pass_dir) / 'meta.json'))
    yd.PX, yd.DSTEP = meta['render_px_m'], meta['depth']['step']          # 판 T: 15.625 cm, 깊이 0.0625 m
    yd.LM_OBJ, yd.LM_BRIDGE, yd.LM_AREA, yd.LM_PX = LM_OBJ, [], LM_AREA, []
    for s in a.steps:
        t = time.time()
        getattr(yd, 'step_' + s)(a)
        if s == 'mapjson': finish_mapjson(a)
        yd.log(f'step {s} done in {time.time() - t:.0f}s')
    if a.install: install(a)


if __name__ == '__main__':
    main()
