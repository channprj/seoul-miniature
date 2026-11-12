# [5차] 판 F 12.5 cm 타일용 사본: 0.5 m 픽셀 = 타일의 4×4 칸 가운데(2::4) 표본. 지면 분류 래스터는 clsF/ground_cls(F 판 범위로 다시 덤프).
# [3차] ID 패스 + 깊이 + 판 전체 지면 분류(cls/ground_cls) → 0.5 m 분류 맵 full/classes_05m.png 와 랜드마크 맵 full/landmarks_05m.png.
# 0.5 m 픽셀 하나 = 6.25 cm 타일의 8×8 칸 가운데(4::8) 표본(경복궁 판 make_classes.py 와 같은 표본점).
# 지면(ID 1) 픽셀은 깊이로 월드 점을 되살려(z 포함) 지면 분류 래스터에서 찾는다 → 수면(WL −1.8 m)·호안 경사도 정확한 자리.
import json, sys, os, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from cam import Cam, PX
Image.MAX_IMAGE_PIXELS = None
D = 'halfF'; NI, NJ, TW, TH = 8, 8, 2752, 1696; K = 4; PXT = 0.125
# 번호표(경복궁 판 0–11 체계를 잇는다; 4·7 은 여의도에 없음)
NAMES = {0: '바탕 지면(주거·상업 부지, 나대지, 모래)', 1: '도로(간선·이면 차도)', 2: '광장·보도(보도, 산책로, 자전거길, 포장 광장, 주차장, 놀이터)', 3: '잔디·숲 바닥(일반 잔디, 경기장, 숲 바닥)',
         4: '(미사용: 경복궁 마당)', 5: '강물(한강)', 6: '일반 건물(저층, 합성 저층, 아파트, 공원 정자)', 7: '(미사용: 경복궁 한옥)', 8: '타워(h≥45 m 업무 빌딩)',
         9: '랜드마크(국회 일원, 63, 파크원, IFC, LG, FKI, KBS, 교회, 더현대, 거래소 등)', 10: '교량(상판·교각·램프)', 11: '나무', 12: '철도·역(선로 바닥, 역사, 승강장, 출입구)',
         13: '호안(사석 경사, 계단식, 샛강 둑)', 14: '공원 잔디마당(비워 둔 잔디)', 15: '습지(갈대)', 16: '선착장·부잔교', 17: '작은 물(연못, 샛강 수로, 수영장)'}
# gen_area 지면 분류(0–28) → 위 번호
GMAP = {0: 0, 1: 0, 2: 0, 3: 3, 4: 3, 5: 5, 6: 17, 7: 0, 8: 3, 9: 2, 10: 2, 11: 0, 12: 12, 13: 2, 14: 1, 15: 1, 16: 2, 17: 2, 18: 16, 19: 13, 20: 2,
        21: 2, 22: 17, 23: 15, 24: 14, 25: 13, 26: 13, 27: 16, 28: 3}
def obj_class(kind):
    k = kind.split(':')[0]
    if k == 'landmark': return 9
    if k == 'bridge': return 10
    if k == 'tree': return 11
    if k == 'tower': return 8
    if k.startswith('station'): return 12
    if k in ('lowrise', 'lowrise_synthetic', 'apartment', 'park_pavilion'): return 6
    raise KeyError(kind)
# 프롬프트용 랜드마크 맵(창 안 비율 판정, 타워형 구분). 63 은 타워 본체만 2, 포디움은 13. 10 이상 = 낮은(타워 아닌) 랜드마크
LMK = {'assembly': 1, '63': 2, 'parc1': 3, 'parc2': 4, 'ifc1': 5, 'ifc2': 5, 'ifc3': 5, 'conrad': 5, 'lg': 6, 'fki': 7, 'anchor': 8, 'post': 8,
       '국회의원회관': 9, '국회도서관': 9, '국회의정관': 9, '국회소통관': 9, '국회박물관': 9, 'hyundai': 10, 'church': 11, 'kbs': 12, '63_podium': 13, 'ifc_gate': 14, 'fki_hall': 16}   # [6차] 16 = FKI 컨퍼런스센터(새 종류 landmark:fki_hall, 낮은 랜드마크)
cam = Cam('F'); gj = json.load(open('clsF/ground_cls.json')); G = np.asarray(Image.open('clsF/ground_cls.png'))
gx0, gy1, GT = gj['gx0'], gj['gy1'], gj['GTEX']
cls = np.zeros((NJ * TH // K, NI * TW // K), np.uint8); lmm = np.zeros_like(cls); zs = []; unk = set(); lut_cache = {}
ONLY = [tuple(map(int, x.split('_'))) for x in os.environ['YD_TILES'].split(',')] if os.environ.get('YD_TILES') else None   # 시험용 일부 타일
for j in range(NJ):
    for i in range(NI):
        if ONLY and (i, j) not in ONLY: continue
        t = f'{D}/t_{i}_{j}'; m = json.load(open(t + '_meta.json')); dp = m['depth']
        a = np.asarray(Image.open(t + '_id.png').convert('RGB'))[K // 2::K, K // 2::K]; ids = a[..., 0].astype(np.int32) * 256 + a[..., 1]
        z = np.asarray(Image.open(t + '_z.png').convert('RGB'))[K // 2::K, K // 2::K]; dv = dp['z0'] + (z[..., 0].astype(np.float64) * 256 + z[..., 1]) * dp['step']
        c = np.zeros(ids.shape, np.uint8); l = np.zeros(ids.shape, np.uint8)
        for v in np.unique(ids):
            kd = m['ids'].get(str(int(v)))
            if kd is None: unk.add(int(v)); continue
            if kd == 'ground': continue
            c[ids == v] = obj_class(kd)
            lk = kd.split(':')[1] if kd.startswith('landmark:') else None
            l[ids == v] = LMK.get(lk, 15) if lk else 0   # 15 = 그 밖의 랜드마크(거래소 등)
        gm = ids == 1
        if gm.any():
            Y, X = np.nonzero(gm); Xc = (i * TW + X * K + K / 2 + .5); Yc = (j * TH + Y * K + K / 2 + .5)
            u = cam.SX0 + Xc * PXT; vv = cam.SY1 - Yc * PXT
            bcx, bcy = cam.SX0 + cam.W * PX / 2, cam.SY1 - cam.H * PX / 2; CREF = np.array(dp['cam_ref']); VD = np.array(dp['view_dir'])
            P = CREF + np.outer(u - bcx, cam.EX) + np.outer(vv - bcy, cam.EY) + np.outer(dv[gm], VD)
            zs.append(P[:, 2])
            gi = np.clip(((P[:, 0] - gx0) / GT).astype(int), 0, G.shape[1] - 1); gjx = np.clip(((gy1 - P[:, 1]) / GT).astype(int), 0, G.shape[0] - 1)
            c[Y, X] = np.vectorize(GMAP.get)(G[gjx, gi])
        cls[j * TH // K:(j + 1) * TH // K, i * TW // K:(i + 1) * TW // K] = c; lmm[j * TH // K:(j + 1) * TH // K, i * TW // K:(i + 1) * TW // K] = l
Image.fromarray(cls).save(f'{D}/classes_05m.png'); Image.fromarray(lmm).save(f'{D}/landmarks_05m.png')
zz = np.concatenate(zs); cnt = {int(k): int(v) for k, v in zip(*np.unique(cls, return_counts=True))}
json.dump({'names': NAMES, 'ground_map_from_gen_area': GMAP, 'landmarks_05m': {**{v: [k for k, x in LMK.items() if x == v] for v in sorted(set(LMK.values()))}, 15: ['other']}, 'counts': cnt, 'unknown_ids': sorted(unk),
           'ground_z_check_m': [round(float(np.percentile(zz, q)), 2) for q in (0.1, 1, 50, 99, 99.9)]}, open(f'{D}/classes_05m.json', 'w'), ensure_ascii=False, indent=1)
print('counts', {k: (NAMES[k].split('(')[0], round(v / cls.size * 100, 2)) for k, v in cnt.items()}); print('unknown', sorted(unk)[:20]); print('ground z %', [round(float(np.percentile(zz, q)), 2) for q in (0.1, 1, 50, 99, 99.9)])
