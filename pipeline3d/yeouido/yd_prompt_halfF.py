"""[5차] 여의도 판 F(θ=180) 12.5 cm/px(캔버스 22016×13568) 창용 프롬프트. prompt_for(x0, y0, tw, th) -> str (hd_coord --prompt-module 규약).
좌표는 판 F 의 12.5 cm 캔버스 px 이고, 안에서 ×2 해 yd_prompt(6.25 cm 규약; classes_05m/landmarks_05m 는 0.5 m = 4 px)를 그대로 부른다.
문장·임계값은 yd_prompt 와 같다(리드가 고친 BRIDGE·LM1 문장 포함, 이 파일에는 문장이 없다).
분류 맵 폴더는 YD_FULL(yd_prompt.py 폴더 기준 상대 경로 또는 절대 경로). **이 모듈은 YD_FULL 이 없으면 halfF 로 둔다** — 판 C 의 full/ 맵을 F 좌표로 읽으면 안 된다.
python yd_prompt_halfF.py            대표 창 표 + 270창 격자 통계
python yd_prompt_halfF.py X Y [TW TH] 그 창의 프롬프트 전문"""
import os, sys, math, importlib.util
os.environ.setdefault('YD_FULL', 'halfF')
_s = importlib.util.spec_from_file_location('yd_prompt', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yd_prompt.py'))
_m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)
W, H, K = 22016, 13568, 2
def prompt_for(x0, y0, tw, th): return _m.prompt_for(x0 * K, y0 * K, tw * K, th * K)
def chosen(x0, y0, tw, th): return [k for k, _ in _m.chosen(x0 * K, y0 * K, tw * K, th * K)]
def features(x0, y0, tw, th): return _m.features(x0 * K, y0 * K, tw * K, th * K)
def _grid(total, size, ov=128):   # hd_coord.grid 와 같다
    n = math.ceil((total - ov) / (size - ov)); step = (total - size) / (n - 1)
    p = [int(round(i * step / 16)) * 16 for i in range(n)]; p[-1] = total - size; return p
def _row(nm, x, y, tw=1408, th=1024):
    f, lm = features(x, y, tw, th); ch = chosen(x, y, tw, th)
    lms = ' '.join(f'{k}:{a:.2f}/{b:.2f}' for k, (a, b) in lm.items() if a > 0)
    return (f'| {nm} | {x},{y} | {f[5]:.2f} | {f[10]:.2f} | {f[8]+f[18]:.2f} | {f[14]:.2f} | {f[3]:.2f} | {f[11]:.2f} | {f[13]:.3f} | '
            f'{f[0]+f[2]+f[3]+f[13]+f[14]+f[15]+f[16]:.2f} | {lms or "-"} | {" ".join(ch)} | {len(prompt_for(x, y, tw, th))} |')
if __name__ == '__main__':
    if len(sys.argv) > 2:
        a = list(map(int, sys.argv[1:])) + [1408, 1024]; print(prompt_for(*a[:4])); sys.exit()
    HDR = '| 창 | x0,y0(12.5 cm) | 강 | 교량 | 타워(+타워형 랜드) | 공원잔디 | 잔디 | 나무 | 호안 | 열린면 | 랜드마크(건물 중 창 안/창 점유) | 선택 문장 | 길이(자) |\n|' + '---|' * 13
    # 대표 창: 판 C 대표 창(3차, 6.25 cm 좌표)의 가운데가 가리키는 지면 점을 판 F 로 옮겨 그 점을 창 가운데에 둔다.
    #   건물 창(국회·파크원·63·더현대)은 landmarks_05m 에서 그 건물 픽셀의 무게중심을 가운데에 둔다(지면 점으로 옮기면 높은 건물은 창을 벗어난다).
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from cam import Cam
    cC, cF = Cam('C'), Cam('F'); _m._load()
    def clampw(cx, cy): return int(min(W - 1408, max(0, cx - 704)) // 16 * 16), int(min(H - 1024, max(0, cy - 512)) // 16 * 16)
    def viaC(x, y):
        X, Y = cF.proj(cC.unproj(x + 704, y + 512, 0.0)); return clampw(X / 2, Y / 2)
    def lmc(ks):
        yy, xx = np.nonzero(np.isin(_m._L, ks)); return clampw(xx.mean() * 4, yy.mean() * 4) if len(yy) else None
    REP = [('국회 본관', lmc([1])), ('여의도공원', viaC(25813, 13592)), ('물빛광장', viaC(21174, 19238)), ('파크원', lmc([3, 4])), ('63빌딩', lmc([2])),
           ('더현대', lmc([10])), ('강 위 교량(마포대교)', viaC(22312, 23536))]
    print('대표 창(1408×1024 = 176×128 m), 판 F'); print(HDR)
    for nm, xy in REP:
        if xy: print(_row(nm, *xy))
        else: print(f'| {nm} | 판 밖 |')
    # 시험 블록(2×2 창, 겹침 128 → 2688×1920): 판 C 시험 블록(ydtest.sh)과 같은 대상. 왼쪽 위 창 원점
    TB = [('asm', lmc([1])), ('b63', lmc([2])), ('biz', lmc([3, 4])), ('riv', viaC(22312 - 1408, 23536 - 3000))]
    for nm, xy in TB:
        if not xy: continue
        x, y = min(W - 2688, max(0, xy[0] - 640)) // 16 * 16, min(H - 1920, max(0, xy[1] - 448)) // 16 * 16
        print(f'| **시험 블록 {nm}: 원점 {x},{y} (2688×1920)** |')
        for dx, dy in ((0, 0), (1280, 0), (0, 896), (1280, 896)): print(_row(f'시험 {nm} +{dx},{dy}', x + dx, y + dy))
    xs, ys = _grid(W, 1408), _grid(H, 1024); from collections import Counter
    cn = Counter(); nsent = Counter(); lmw = {s: [] for s in _m.LM}; best = {}; longest = (0, None)
    for y in ys:
        for x in xs:
            ch = chosen(x, y, 1408, 1024); cn.update(ch); nsent[len(ch)] += 1; f, lm = features(x, y, 1408, 1024)
            L = len(prompt_for(x, y, 1408, 1024)); longest = max(longest, (L, (x, y, ' '.join(ch))))
            for k, (a, b) in lm.items():
                if a > best.get(k, (0,))[0]: best[k] = (round(a, 2), round(b, 2), x, y)
                s = _m.LMAP[k]
                ta, tb = _m.LTHR.get(k, (0.35, 0.35))
                if (a >= ta or b >= tb) and (x, y) not in [w[:2] for w in lmw[s]]: lmw[s].append((x, y, k, round(a, 2), round(b, 2)))
    print(f'\n격자(hd_coord.grid, 겹침 128): {len(xs)}×{len(ys)} = {len(xs) * len(ys)}창'); print('문장별 창 수:', dict(cn)); print('창당 문장 수 분포:', dict(sorted(nsent.items())))
    print('가장 긴 프롬프트:', longest)
    print('랜드마크별 최대 (건물 중 창 안 비율, 창 점유, 그 창 x,y):', {k: best.get(k) for k in _m.LMAP})
    for s, nm in ((1, '국회'), (2, '63'), (3, '파크원'), (4, '더현대'), (5, 'IFC·콘래드')): print(f'LM{s} {nm} 문장이 들어가는 창 {len(lmw[s])}곳:', lmw[s])
