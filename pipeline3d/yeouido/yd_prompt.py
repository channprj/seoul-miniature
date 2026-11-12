"""[3차] 여의도 판 C 창별 양식 프롬프트. prompt_for(x0, y0, tw, th) -> str (6.25 cm 전체 좌표, hd_coord --prompt-module 규약).
gyeongbokgung/p3d_prompt.py 머리 주석의 교훈을 따른다:
 - 승인된 일반 동네 문구 M1 을 그대로(p3d_prompt 에서 import) 쓰고, 창에 실제로 있는 것에 대한 짧은 문장만 KEY 앞에 끼운다.
   문구를 길게 새로 쓰면 픽셀아트로 다시 그리지 않고 3D 렌더에 소품만 얹는다.
 - 창에 없는 것을 언급하면 지어낸다 → 모든 문장은 classes_05m / landmarks_05m 로 창 안에 있을 때만 넣는다.
   M1 의 한옥 두 문장은 여의도 판에 한옥이 없으므로(분류 7 = 0) 지운다. 고쳐 쓰지 않고 지우기만 한다.
 - 넓은 빈 땅에서는 건물·소품을 지어내므로, 열린 면이 넓은 창에는 '그대로 둔다' 문장(KEEP, PAL 에서 검증된 문구)을 넣는다.
 - 랜드마크 문장은 그 건물이 창에 충분히 들어온 창에만(경복궁 r1: 문이 안 보이는 이웃 창에 문 문장 → 문을 여러 채 지어냄).
   기준 35%: (건물의 0.5 m 픽셀 중 창 안 비율) ≥ 0.35 또는 (창 면적 중 그 건물 비율) ≥ 0.35.
   뒤의 조건은 여의도에서 더했다 — 1408×1024 창(88×64 m)에는 63(화면 높이 약 200 m)·파크원이 35% 넘게 들어갈 수 없어 앞 조건만으로는 끝내 안 걸린다.
full/classes_05m.png 번호: 0 바탕 1 도로 2 광장·보도 3 잔디·숲바닥 4 (미사용) 5 강물 6 일반건물 7 (미사용) 8 타워 9 랜드마크 10 교량 11 나무 12 철도·역
 13 호안 14 공원 잔디마당 15 습지 16 선착장 17 작은 물.  full/landmarks_05m.png: 1 국회 본관 2 63 3 파크원1 4 파크원2 5 IFC·콘래드 6 LG 7 FKI 8 앵커원·포스트타워 9 국회 부속동 10 더현대 11 순복음교회 12 KBS 13 63 포디움 14 IFC 몰 입구 15 기타(거래소 등) 16 FKI 컨퍼런스센터([6차] landmark:fki_hall)
GPU·모델 실행 없음. 이 모듈은 문자열만 만든다."""
import os, importlib.util, numpy as np
from PIL import Image
_H = os.path.dirname(os.path.abspath(__file__)); _C = _L = None; _LTOT = None
_spec = importlib.util.spec_from_file_location('p3d_prompt', os.path.join(_H, '..', 'gyeongbokgung', 'p3d_prompt.py'))
_p3d = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_p3d)
M1, KEY, TOWER, TREE, LAWN = _p3d.M1, _p3d.KEY, _p3d.TOWER, _p3d.TREE, _p3d.LAWN   # 검증된 문장은 그대로 가져온다
HANOK = ("Dark charcoal ribbed roofs are hanok, traditional Korean houses: grey-black giwa tile roofs with crisp tile rows, ridge lines and slightly upturned eaves, "
         "wooden posts and paper lattice doors. Hanok roofs are plain unbroken tile: no skylights, no windows, no objects on them. ")
assert KEY in M1 and HANOK in M1
KEEP = "Do not invent buildings or objects in empty areas. "          # PAL 문구에서 검증된 문장
RIVER = "The wide blue area is the Han River: keep it open water with only small ripple marks; do not add boats, islands or bridges on it. "
BRIDGE = "The long straight grey strips crossing the water are road bridges: each deck is an empty asphalt road with lane markings and side railings only, on concrete piers. Never draw buildings, houses, shops, rooftops or any objects on a bridge; keep every deck, pier and railing exactly as rendered. "
BANK = "The river edge is a stone embankment: keep its sloped stone band and concrete steps at the water exactly as rendered, no sand beach. "
PARK = "Bright green open lawns in the park stay empty mown grass with nothing added on them; the trees stay exactly where they are. "
LM = {1: "The large pale stone hall with the teal-green dome is the National Assembly building, a monumental government hall, not an apartment or shop building: keep its pale grey granite walls, the ring of tall plain stone columns on every side, the flat blue roof deck with its pale stone rim around the green dome, the stone base and wide steps exactly as rendered. Its walls are pale stone with tall narrow windows, never brick; draw no shopfronts, awnings or signs on it and add nothing to its roof. ",
      2: "The gold glass tower is the 63 Building: keep its smooth warm gold-bronze glass walls with a fine even grid on every face, the blue-grey lift strip running up its narrow end face, its dark bands and its outline exactly as rendered. It is the only gold building; its walls are gold glass from the ground to the top, never brick, never pale panels, never pink. ",
      3: "The two tallest towers with thin red steel columns are Parc One: keep the pairs of red columns at both ends of each face running the full height, and the same blue-grey glass window bands on every floor (never brick, never white panels) exactly as rendered. Only these two towers have red columns: draw no red frames, red columns or red roof edges on any other tower or office block. ",
      4: "The low wide hall with eight red leaf-shaped truss masts along its long sides is a department store: keep its grey roof, the dark green roof-garden squares with small glass skylights and the red masts exactly as rendered. Its roof is grey and green, never white; add nothing on it. ",
      5: "The pale silver-blue glass towers with slanted, faceted sides are IFC Seoul: keep their cut-crystal shapes, sloped pale-rimmed roof decks and smooth glass grid exactly as rendered; do not square them off. "}
# [8차, 리드 11-11] 지붕 문장은 그 건물 꼭대기가 창 안에 있을 때만(꼭대기가 없는 창에 헬리패드·지붕을 말하면 벽 중간에 지붕을 지어낸다: ydF4_biz, ydF4_b63).
LMROOF = {2: "The 63 Building's pale flat roof with the plain ring helipad stays exactly as rendered. ",
          3: "Each Parc One tower ends in an eight-sided top with a beige rim band and a square grey helipad marked only by a white outline and a circle, no letters; keep it exactly as rendered. "}
CUT = "Some tall towers continue past the top or bottom edge of this picture: there the same wall and the same window grid simply run on to the edge, unbroken, in one piece. "
LMAP = {1: 1, 2: 2, 3: 3, 4: 3, 10: 4, 5: 5}   # landmarks_05m 값 → 문장(파크원 두 동은 한 문장; [6차] 10 더현대 → LM4, 5 IFC·콘래드 4동 묶음 → LM5)
LTHR = {5: (0.15, 0.10), 3: (0.30, 0.25)}   # [7차] 파크원1: 넓은 지붕 판이 팔각 꼭대기로 바뀌어 화소가 줄었다(꼭대기 창 9696,3584 가 0.34/0.26 으로 빠짐) → 기준을 낮춰 다시 넣는다.
_LTHR6 = {5: (0.15, 0.10)}   # [6차] 묶음(IFC 4동)은 한 동만 들어와도 걸리게: (묶음 중 창 안 비율, 창 점유) 기준. 나머지는 (0.35, 0.35)
MAXS = 7; DROP = ['LAWN', 'BANK', 'PARK', 'TREE', 'LM4', 'KEEP']   # [6차] 문장 수 상한과, 넘을 때 빼는 순서(긴 프롬프트는 다시 그리지 않고 소품만 얹는다)
TOWERLM = [2, 3, 4, 5, 6, 7, 8]   # 띠창 타워인 랜드마크. 국회(1·9)·더현대·교회·KBS·포디움은 TOWER 문장에 넣지 않는다(11-11 표: 국회 창에 타워 문장이 들어감)
# [7차, 리드 11-11] 건물 속성별 문장: M1 의 옥상 소품·벽 문장은 2~5층 빌라용이라 타워 옥상에 파라솔·항아리가 올라갔다(사용자: "건물 속성에 따라 다르게").
# 창 안 건물을 저층 / 타워(랜드마크 타워 포함) / 아파트로 나눠, 있는 종류에 대한 문장만 넣는다. 종류 맵은 cond_id + meta 에서 0.5 m 로 만든다(types_05m.npy 캐시).
VILLA = "Flat-roofed 2-5 storey buildings are Seoul villa houses and shop-houses; each looks a little different. "
ROOF = "Each flat rooftop stays mostly open and keeps its green or grey colour, with only two to four small things on it, chosen from: a water tank, a couple of planters, a few brown onggi jars, a short laundry line, one parasol with a table, a satellite dish, a cooling unit, a solar panel. "
WALL = "Walls get brick courses, varied window frames, a few balconies, air conditioner units and drain pipes; some ground floors have a shop front with a plain awning and a blank signboard. "
assert VILLA in M1 and ROOF in M1 and WALL in M1
B_LOW = ("Low flat-roofed 2-5 storey buildings are shop-houses and small offices; each looks a little different. Their rooftops stay mostly open and keep their green or grey colour, with only two to four small things, chosen from: a water tank, a couple of planters, a few brown onggi jars, one parasol with a table, a satellite dish, a cooling unit, a solar panel. "
         "Their walls get brick courses, varied window frames, air conditioner units and drain pipes; some ground floors have a shop front with a plain awning and a blank signboard. ")
# [7차 워커] 타워 옥상에는 이제 헬리패드(네모 판 + 흰 테두리 + 원)·기계실·태양광이 모델링돼 있다 → "chosen from"(리드 판: yd_prompt_v7_lead.py)은 그 위에 또 얹으라는 말이 되므로
# "그린 대로 두고 작은 것 하나까지만"으로 바꿨다. 헬리패드 글자 금지도 여기에(LG·일반 타워·페어몬트 공통).
B_TOWER = ("Tall office towers are sleek modern high-rises: keep every tower roof exactly as rendered and add nothing to it. "
           "Tower walls are clean glass and panel grids from the ground to the top, never brick, with no balconies, awnings or air conditioner boxes; only the ground floor may have a glass lobby. ")
B_APT = ("Tall slab blocks with long rows of identical windows are apartment blocks: pale painted concrete walls with regular rows of windows and enclosed balconies, never brick; "
         "each apartment roof has only a small stair-and-lift box and a water tank, nothing else. ")
_T = None
def _types():
    global _T
    if _T is None:
        import json
        d = os.path.join(_H, os.environ.get('YD_FULL', 'full')); f = os.path.join(d, 'types_05m.npy')
        if os.path.exists(f): _T = np.load(f)
        else:
            Image.MAX_IMAGE_PIXELS = None
            im = Image.open(os.path.join(d, 'cond_id.png')); k = round(0.5 / json.load(open(os.path.join(d, 'meta.json')))['px_m'])
            a = np.asarray(im)[k // 2::k, k // 2::k]; ids = a[..., 0].astype(np.int32) * 256 + a[..., 1]
            lut = np.zeros(65536, np.uint8)
            for i, t in json.load(open(os.path.join(d, 'meta.json')))['ids'].items():
                t0 = t.split(':')[0]
                lut[int(i)] = 1 if t0 in ('lowrise', 'lowrise_synthetic', 'station_building') else 2 if t0 == 'tower' else 3 if t0 == 'apartment' else 0
            _T = lut[ids]; np.save(f, _T)
    return _T
def btypes(x0, y0, tw, th):
    """창 안 건물 화소 중 (저층, 타워, 아파트) 비율과 건물 화소의 창 점유. 타워형 랜드마크는 타워로 센다."""
    _load(); T = _types(); sl = (slice(max(0, y0 // 8), max(0, (y0 + th) // 8)), slice(max(0, x0 // 8), max(0, (x0 + tw) // 8)))
    t = T[sl]; l = _L[sl][:t.shape[0], :t.shape[1]]; t = t[:l.shape[0], :l.shape[1]]
    lo = float((t == 1).sum()); to = float((t == 2).sum() + np.isin(l, TOWERLM).sum()); ap = float((t == 3).sum()); n = lo + to + ap
    return (lo / max(1, n), to / max(1, n), ap / max(1, n), n / max(1, t.size))
def base_for(x0, y0, tw, th):
    lo, to, ap, occ = btypes(x0, y0, tw, th)
    if occ < 0.01 or to + ap < 0.12: return M1          # 저층 동네(또는 건물 없음): 승인된 문구 그대로
    s = (B_LOW if lo >= 0.12 else '') + (B_TOWER if to >= 0.12 else '') + (B_APT if ap >= 0.12 else '')
    return M1.replace(VILLA, '').replace(ROOF, '').replace(WALL, s)
def _load():
    global _C, _L, _LTOT
    if _C is None:
        d = os.path.join(_H, os.environ.get('YD_FULL', 'full'))
        _C = np.asarray(Image.open(os.path.join(d, 'classes_05m.png'))); _L = np.asarray(Image.open(os.path.join(d, 'landmarks_05m.png')))
        _LTOT = {k: int((_L == k).sum()) for k in LMAP}
def features(x0, y0, tw, th):
    """창의 분류 비율 f[0..17] 와 랜드마크별 (건물 중 창 안 비율, 창 중 건물 비율)."""
    _load()
    sl = (slice(max(0, y0 // 8), max(0, (y0 + th) // 8)), slice(max(0, x0 // 8), max(0, (x0 + tw) // 8)))
    c = _C[sl]; l = _L[sl]; n = max(1, c.size)
    f = [float((c == k).sum()) / n for k in range(18)]
    lm = {k: ((float((l == k).sum()) / _LTOT[k]) if _LTOT[k] else 0.0, float((l == k).sum()) / n) for k in LMAP}
    f.append(float(np.isin(l, TOWERLM).sum()) / n)   # f[18] = 타워형 랜드마크 비율
    return f, lm
def chosen(x0, y0, tw, th):
    """끼울 문장 이름 목록(순서대로)."""
    f, lm = features(x0, y0, tw, th); out = []
    for s in sorted({LMAP[k] for k, (fin, fwin) in lm.items() if fin >= LTHR.get(k, (0.35, 0.35))[0] or fwin >= LTHR.get(k, (0.35, 0.35))[1]}): out.append(('LM%d' % s, LM[s]))
    sl = (slice(max(0, y0 // 8), max(0, (y0 + th) // 8)), slice(max(0, x0 // 8), max(0, (x0 + tw) // 8))); l = _L[sl]
    for sn in (2, 3):
        if not any(k == 'LM%d' % sn for k, _ in out): continue
        for kk in (k for k, v in LMAP.items() if v == sn):
            rows = np.nonzero((_L == kk).any(1))[0]
            if len(rows) and sl[0].start <= rows[0] < sl[0].stop - 12 and (_L[rows[0]:rows[0] + 12, sl[1]] == kk).any():
                out.append(('ROOF%d' % sn, LMROOF[sn])); break
    T = _types()[sl]; tw_ = (T == 2)[:l.shape[0], :l.shape[1]] | np.isin(l, TOWERLM)[:T.shape[0], :T.shape[1]]
    if tw_.size and (tw_[:3].mean() > 0.04 or tw_[-3:].mean() > 0.04): out.append(('CUT', CUT))
    haslm1 = any(k == 'LM1' for k, _ in out)
    if f[8] + f[18] > 0.03: out.append(('TOWER', TOWER))
    if f[10] > 0.01: out.append(('BRIDGE', BRIDGE))
    if f[5] > 0.05: out.append(('RIVER', RIVER))
    if f[13] > 0.004 and f[5] + f[17] > 0.02: out.append(('BANK', BANK))
    if f[14] > 0.02: out.append(('PARK', PARK))
    if f[3] > 0.02 and f[14] <= 0.02: out.append(('LAWN', LAWN))   # PARK 와 같이 쓰지 않는다(문장 수 줄이기)
    if f[11] > 0.003: out.append(('TREE', TREE))
    openf = f[0] + f[2] + f[3] + f[13] + f[14] + f[15] + f[16]
    if openf > 0.35 or (f[5] > 0.05 and f[6] + f[8] + f[9] < 0.1) or haslm1: out.append(('KEEP', KEEP))   # [6차] 국회 창에는 항상 KEEP(앞마당·지붕 소품)
    for d in DROP:
        if len(out) <= MAXS: break
        out = [o for o in out if o[0] != d]
    return out
def prompt_for(x0, y0, tw, th):
    _load(); add = ''.join(s for _, s in chosen(x0, y0, tw, th))
    p = base_for(x0, y0, tw, th); p = p if (_C == 7).any() else p.replace(HANOK, '')
    return p.replace(KEY, add + KEY)
if __name__ == '__main__':   # 대표 창 선택 표
    import sys
    W = [('wasm 국회', 42200, 10470), ('wpark 여의도공원', 25813, 13592), ('wmulbit 물빛광장', 21174, 19238), ('wbiz 파크원/IFC', 22758, 9664),
         ('w63 63빌딩', 1274, 16060), ('whyundai 더현대', 21016, 13783), ('wbridge 강 위 교량', 22312, 23536)]
    print('| 창 | x0,y0 | 강 | 교량 | 타워(+타워형 랜드) | 공원잔디 | 잔디 | 나무 | 호안 | 열린면 | 랜드마크(창안비율/창점유) | 선택 문장 | 길이(자) |'); print('|' + '---|' * 13)
    for nm, x, y in W:
        f, lm = features(x, y, 1408, 1024); ch = [k for k, _ in chosen(x, y, 1408, 1024)]
        lms = ' '.join(f'{k}:{a:.2f}/{b:.2f}' for k, (a, b) in lm.items() if a > 0)
        print(f'| {nm} | {x},{y} | {f[5]:.2f} | {f[10]:.2f} | {f[8]+f[18]:.2f} | {f[14]:.2f} | {f[3]:.2f} | {f[11]:.2f} | {f[13]:.3f} | {f[0]+f[2]+f[3]+f[13]+f[14]+f[15]+f[16]:.2f} | {lms or "-"} | {" ".join(ch)} | {len(prompt_for(x, y, 1408, 1024))} |')
    if len(sys.argv) > 1: print(prompt_for(*map(int, sys.argv[1:5])))
