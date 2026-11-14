# -*- coding: utf-8 -*-
"""랜드마크 타워에 덧붙이는 형태(lm_build.py 가 parnas.py 다음에 exec 한다). 네이버 지도 거리뷰·항공뷰·위성 화면과 위키미디어 공용 사진을 2026-11-13·14 에 눈으로 보고 옮겼다.
  삼성 서초사옥 세 동(samsung()): 한 동이 통짜 상자가 아니라, 높은 몸통 옆에 높이가 다른 유리 상자들이 붙어 계단처럼 오르는 꼴이다. 덩어리마다 줄의 방향이 다르다(층마다 밝은 가로줄 / 밝은 세로 핀).
        도면 — ArchDaily 에 실린 KPF 도면 네 장(배치도, 위치도, B동·C동 평면도)과 대조했다(2026-11-14). 평면 구성은 도면을 따른다: 세 동과 따로 선 북쪽 별동, C동 타워가 윤곽의 북쪽 76 % 에 서는 것,
          A·B동이 긴 축으로 나란한 두 판으로 이루어지고 B동은 남쪽 판이 서쪽으로 밀려 있는 것. 단면도·입면도는 공개된 것을 찾지 못해 높이 구성은 아래 사진에서 읽었다.
        본 것 — 네이버 항공뷰(2009-03 촬영, 남쪽 상공 6곳)와 위키미디어 공용 사진 「Samsung headquarters.jpg」(북동쪽에서), 거리뷰:
          삼성전자 동: 남쪽 끝의 낮은 기단(옥상에 초록 줄), 그 뒤 중간 덩어리(가로줄), 북쪽의 높은 몸통은 동쪽의 가로줄 판(꼭대기에 짙은 띠)과 서쪽의 조금 낮은 세로 핀 판. 가로줄 판 아래는 세로 핀이고 그 사이에 몇 층 들어간 허리가 있다.
          삼성화재 동: 동서로 긴 몸통(세로 핀, 옥상 동쪽 끝에 헬리패드)과 남서쪽 앞의 낮은 상자.
          삼성생명 동: 몸통(헬리패드), 동쪽에 붙은 조금 낮은 판(옥상 정원), 남서쪽의 낮은 덩어리(옥상 정원), 북서쪽에 중간 높이부터 꼭대기까지 밖으로 내민 세로 핀 유리 상자.
        어림 — 덩어리를 나누는 자리(윤곽의 몇 할)와 높이는 사진 비례로 잡았다(오차 10 % 안팎). 내민 폭 2~4 m, 헬리패드 크기도 어림이다. 틈 밑의 그늘은 위에서 보는 그림이라 따로 칠하지 않았다
        (앞 판은 그 자리를 짙은 판으로 칠해 전광판처럼 보였다 — 실제로는 유리 상자가 밖으로 나와 있을 뿐이다). prep_extra.py 가 전자 동을 타워와 북쪽 별동으로 나누고 생명 동의 윤곽을 고친다.
  메리츠타워: 옥상을 두른 비스듬한 금속 틀(북서 변이 높고 남동 변이 낮다. 위성 화면에서는 헬리패드를 두른 흰 테로 보인다). 높이 12 m 는 어림.
  강남역 지하쇼핑센터: 지하 상가(OSM location=underground)가 69 m 건물로 서 있던 것을 뺀다.
  GS타워: 긴 면은 밝은 은회색 격자(lm_build.py 의 LMC), 서쪽 끝면은 짙은 반사 유리에 검은 세로 줄 하나와 꼭대기의 계단꼴 검은 홈, 'GS타워' 글자(일반 글꼴).
"""
cmb = MB()
def _sstex(kind, glass, line, flh=4.2):
    """삼성 서초사옥 유리. 'h' = 층마다 밝은 가로줄(+ 옅은 세로 이음), 'v' = 밝은 세로 핀(+ 옅은 층 줄). 핀 간격 3 m 는 그림에서 읽히게 실제의 두 배."""
    W, Hh = 12.0, 2 * flh
    def draw(d):
        w, h = int(W * RPPM), int(Hh * RPPM)
        for f in range(2):
            y = int((f + 1) * flh * RPPM)
            if kind == 'h': d.rectangle([0, y - int(1.0 * RPPM), w, y - 1], fill=line); d.rectangle([0, y - int(1.25 * RPPM), w, y - int(1.0 * RPPM) - 1], fill=shade(glass, .8))
            else: d.rectangle([0, y - int(.3 * RPPM), w, y - 1], fill=shade(glass, .82))
        for k in range(4):
            x = int(k * 3.0 * RPPM)
            if kind == 'h': d.rectangle([x, 0, x + int(.22 * RPPM), h], fill=shade(glass, .86))
            else: d.rectangle([x, 0, x + int(.8 * RPPM) - 1, h], fill=line)
    return mat_tex(_png(f'ss{kind}_{glass[1:]}_{line[1:]}', int(W * RPPM), int(Hh * RPPM), glass, draw), f'ss{kind}{glass}{line}'), W, Hh
def samsung(b, idx, cfg):
    """삼성 서초사옥 한 동을 유리 상자 여러 개로 세운다. 윤곽을 두른 최소 직사각형에서 u(cfg['ud'] 쪽)·v(cfg['vd'] 쪽)를 0..1 로 재고,
    cfg['boxes'] 의 상자마다 r = (u0, u1, v0, v1)(0..1 밖이면 그만큼 윤곽 밖으로 내민다), z = (아래, 위) ÷ 전체 높이, k = 줄 방향('h'|'v'|'d' 짙은 허리),
    cut = 빼낼 직사각형들, top = 'main'(파라펫·기계실·헬리패드) | 'garden'(옥상 정원) | 'green'(초록 줄) | None, crown = 꼭대기 짙은 띠, heli = 헬리패드 자리 (u, v)."""
    poly = orient(P(b['rings']), 1.0); H = b['h']; mb = MB(); mc = mrr_axes(poly)[4]; c0 = np.mean(mc, axis=0); e0, e1 = mc[1] - mc[0], mc[2] - mc[1]
    ud, vd = np.array(cfg['ud'], float), np.array(cfg['vd'], float); L0, L1 = float(np.hypot(*e0)), float(np.hypot(*e1)); e0, e1 = e0 / L0, e1 / L1
    (u, Lu), (v, Lv) = ((e0, L0), (e1, L1)) if abs(e0 @ ud) >= abs(e1 @ ud) else ((e1, L1), (e0, L0)); u = u if u @ ud > 0 else -u; v = v if v @ vd > 0 else -v
    at = lambda s_, t_: c0 + u * (s_ - .5) * Lu + v * (t_ - .5) * Lv
    rect = lambda u0, u1, v0, v1: Polygon([tuple(at(u0, v0)), tuple(at(u1, v0)), tuple(at(u1, v1)), tuple(at(u0, v1))])
    for bx in cfg['boxes']:
        u0, u1, v0, v1 = bx['r']; pb = max(0.0, -u0 * Lu, (u1 - 1) * Lu, -v0 * Lv, (v1 - 1) * Lv)
        g = (poly.buffer(pb, join_style=2) if pb else poly).intersection(rect(u0, u1, v0, v1))
        for r_ in bx.get('cut', ()): g = g.difference(rect(*r_))
        if bx.get('inset'): g = g.buffer(-bx['inset'], join_style=2)
        g = max(parts(g), key=lambda q: q.area) if not g.is_empty else None
        if g is None or g.area < 20: continue
        g = orient(g, 1.0); z0, z1 = H * bx['z'][0], H * bx['z'][1]; k = bx['k']
        if z0 == 0 and k != 'd': _lobby(mb, g, cfg['lobby'], cfg['glass'], cfg['spc'], cfg['line']); z0 = cfg['lobby']
        if k == 'd': m, tw, th = mat_flat('#2f4466'), 1, 1                                   # 들어간 허리: 그늘진 유리
        else: m, tw, th = _sstex(k, cfg['glass'] if k == 'h' else shade(cfg['glass'], .9), cfg['fin'])
        skin(mb, g, z0, lambda x, y, z1=z1: z1, m, tw, th); capf(mb, g, lambda x, y, z1=z1: z1, mat_flat('#c4c8cc'))
        if bx['z'][0] > 0: capf(mb, g, lambda x, y, z0=z0: z0, mat_flat('#2b3644'))          # 내민 상자의 밑면
        top = bx.get('top'); gc, gax, gLx, gLy, _ = mrr_axes(g); gax = np.array(gax, float)
        if bx.get('crown'): skin(mb, orient(g.buffer(.3, join_style=2), 1.0), z1 - 5.0, lambda x, y, z1=z1: z1 + .2, mat_flat('#34404e'), 1, 1)
        if top: _parapet(mb, g, z1, '#c3d0dc')
        if top == 'main':
            hc = at(*bx['heli']); hh = min(8.0, .3 * gLy); dk = Polygon([tuple(hc + gax * sx * hh + np.array([-gax[1], gax[0]]) * sy * hh) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
            obox(mb, hc, gax, hh, hh, z1, z1 + 3.0, mat_flat('#9aa2aa'), mat_flat('#b9bdc2')); helipad(mb, hc, gax, z1 + 3.0, hh * .92, '#aab0b6', '#ffffff', 'circle', .3)
            roof_std(mb, g, z1, dk, z1 + 3.0, True, b['seed'])
            for q in parts(g.buffer(-1.5, join_style=2).difference(dk.buffer(.05))):
                if q.area > 6: capf(mb, orient(q, 1.0), lambda x, y, z1=z1: z1 + .09, mat_flat(cfg['deck']))
        elif top in ('garden', 'green'):
            inn = g.buffer(-2.2, join_style=2)
            if top == 'garden':
                for q in parts(inn): capf(mb, orient(q, 1.0), lambda x, y, z1=z1: z1 + .12, mat_flat('#8ea765'))
            else:   # 초록 줄(기단 옥상의 식재 띠)
                for t_ in np.arange(-gLy * .3, gLy * .3, 2.4):
                    q = Polygon([tuple(gc + gax * sx * gLx * .22 + np.array([-gax[1], gax[0]]) * (t_ + sy * .7)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]).intersection(inn)
                    for q2 in parts(q):
                        if q2.area > 2: capf(mb, orient(q2, 1.0), lambda x, y, z1=z1: z1 + .12, mat_flat('#7fae5a'))
    toonify(mb.build('b%d' % idx, idx))
_SS = dict(glass='#5f8fca', fin='#c6d9ee', line='#3f6aa3', spc='#c3d0dc', lobby=10.0, deck='#c9cbcc')
LMC['samsung_e'] = dict(_SS, ud=(-.36, .93), vd=(.93, .36), boxes=(          # 삼성전자(C동): u = 남 → 북, v = 서 → 동. 배치도에서 타워(코어가 든 큰 직사각형)는 윤곽의 북쪽 76 %
    dict(r=(0, .24, 0, 1), z=(0, .20), k='h', top='green'),                   # 남쪽 끝 기단
    dict(r=(.24, .50, 0, 1), z=(0, .50), k='h', top='plain'),                 # 중간 덩어리
    dict(r=(.50, 1, .36, 1), z=(0, .33), k='v'),                              # 높은 몸통의 아래(세로 핀)
    dict(r=(.50, 1, .36, 1), z=(.33, .38), k='d', inset=3.5),                 # 들어간 허리
    dict(r=(.50, 1.02, .36, 1), z=(.38, 1.0), k='h', top='main', crown=True, heli=(.86, .68)),   # 가로줄 판(가장 높다)
    dict(r=(.50, 1.035, -.04, .36), z=(0, .90), k='v', top='plain')))         # 서쪽 세로 핀 판(조금 낮고 조금 내밀었다)
LMC['samsung_c'] = dict(_SS, ud=(.94, .34), vd=(-.34, .94), boxes=(          # 삼성화재(B동): u = 서 → 동, v = 남 → 북. 평면도: 긴 축으로 나란한 두 판, 남쪽 판이 서쪽으로 약 5.5 m 밀려 있다
    dict(r=(0, 1, .42, 1), z=(0, 1.0), k='h', top='main', heli=(.84, .72)),   # 북쪽 판(깊이의 58 %, 코어·헬리패드)
    dict(r=(-.106, .97, 0, .42), z=(0, .97), k='v', top='plain'),             # 남쪽 판(서쪽으로 밀림)
    dict(r=(-.106, .45, -.12, .10), z=(0, .45), k='h', top='plain')))         # 남서쪽 앞으로 내민 낮은 상자(항공뷰)
LMC['samsung_l'] = dict(_SS, ud=(-.36, .93), vd=(.93, .36), boxes=(          # 삼성생명(A동): u = 남 → 북, v = 서 → 동. 배치도: 나란한 두 판, 서쪽 판이 깊이의 38 % 이고 북쪽 끝이 조금 짧다
    dict(r=(0, 1, .38, .86), z=(0, 1.0), k='h', top='main', heli=(.5, .62)),  # 동쪽 판(코어·헬리패드)
    dict(r=(.08, .92, .86, 1), z=(0, .85), k='v', top='garden'),              # 동쪽 가장자리의 조금 낮은 띠(옥상 정원, 항공뷰)
    dict(r=(0, .89, -.05, .38), z=(0, 1.02), k='v', top='plain')))            # 서쪽 판(세로 핀, 조금 내밀었다)
LMB.update(samsung_e=samsung, samsung_c=samsung, samsung_l=samsung)
def samsung_annex(b, idx):   # 삼성전자 동 북쪽의 낮은 별동. KPF 배치도에서 타워와 약 10 m 떨어진 따로 선 상자라, 남쪽 8 m 를 잘라 틈을 둔다(OSM 윤곽은 둘이 붙어 있다)
    g_ = P(b['rings']); g_ = g_.intersection(shapely.affinity.translate(g_, -.36 * 8.0, .93 * 8.0)); b = dict(b, rings=[list(orient(g_, 1.0).exterior.coords)])
    ltower(b, idx, dict(glass='#3c4d63', line='#27323f', flh=4.2, bay=1.5, sp=.5, spc='#9aa8b6', lobby=8.0, kit=2, heli=False, deck='#6f8f6a'))
SPECIAL['r8311185n'] = samsung_annex
SPECIAL['w305923846'] = lambda b, idx: None   # 강남역 지하쇼핑센터: OSM 에 location=underground 로 올라 있는 지하 상가라 지상에는 아무것도 세우지 않는다(장면의 건물 순번이 밀리지 않게 항목은 그대로 둔다)
_b, _g = _bp('w379232116')   # 메리츠타워
if _b:
    H = _b['h']; ring = [np.array(p[:2]) for p in _g.exterior.coords[:-1]]; c = np.array(_g.centroid.coords[0]); up = np.array([-.39, .92]); n = len(ring)
    t = [float((p - c) @ up) for p in ring]; zt = [H + 1.5 + 12.0 * (ti - min(t)) / (max(t) - min(t)) for ti in t]; mt, md = mat_flat('#8f979e'), mat_flat('#586067')
    out = [p + (p - c) / np.linalg.norm(p - c) * 1.2 for p in ring]; inn = [p - (p - c) / np.linalg.norm(p - c) * 3.5 for p in ring]
    for k in range(n):
        j = (k + 1) % n
        cmb.face([(*out[k], H - 1.0), (*out[j], H - 1.0), (*out[j], zt[j]), (*out[k], zt[k])], mt)   # 바깥 벽
        cmb.face([(*inn[j], H), (*inn[k], H), (*inn[k], zt[k]), (*inn[j], zt[j])], md)               # 안쪽 벽
        cmb.face([(*out[k], zt[k]), (*out[j], zt[j]), (*inn[j], zt[j]), (*inn[k], zt[k])], mt)       # 비스듬한 윗면
_b, _g = _bp('w562011101')   # GS타워 서쪽 끝면
if _b:
    H = _b['h']; ex = [np.array(p[:2]) for p in _g.exterior.coords]; dW = np.array([-.94, -.34])
    k = max((i for i in range(len(ex) - 1) if np.linalg.norm(ex[i + 1] - ex[i]) > 15), key=lambda i: float((ex[i] + ex[i + 1]) / 2 @ dW)); a, L = ex[k], float(np.linalg.norm(ex[k + 1] - ex[k])); tg = (ex[k + 1] - a) / L; nv = np.array([tg[1], -tg[0]])
    at = lambda f: a + tg * L * f - nv * 2.0; dk, ln, bk = mat_flat('#2e343a'), mat_flat('#434b53'), mat_flat('#14171a')
    wall_strip(cmb, _g, nv, .3, H + 1.0, dk, w=L - .4, off=.3, org=at(.5))
    for z in np.arange(8.0, H - 1, 4.2): wall_strip(cmb, _g, nv, z, z + .18, ln, w=L - .4, off=.34, step=4.0, org=at(.5))
    wall_strip(cmb, _g, nv, .3, H + 1.0, bk, w=1.6, off=.4, org=at(.22))
    for i_, f in enumerate((.62, .68, .74)): wall_strip(cmb, _g, nv, H - 11.0 + 2.5 * i_, H - 4.5 + 2.5 * i_, bk, w=2.2, off=.42, org=at(f))
    pth, asp = sign_png('gstower', 'GS타워', '#e9ecee', '#2e343a', ('AppleGothic.ttf',)); wall_strip(cmb, _g, nv, H - 6.2, H - 3.0, mat_tex(pth, 'sg_gstower'), aspect=asp, off=.44, org=at(.42))
if cmb.f: toonify(cmb.build('lm_crowns', 9793)); META[9793] = 'landmark:signs'
