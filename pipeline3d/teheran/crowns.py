# -*- coding: utf-8 -*-
"""랜드마크 타워에 덧붙이는 형태(lm_build.py 가 parnas.py 다음에 exec 한다). 네이버 지도 거리뷰와 위성 화면을 2026-11-13·14 에 눈으로 보고 옮겼다.
  삼성 서초사옥 세 동(samsung()): 파란 반사 유리 상자를 어긋나게 쌓은 꼴. 덩어리마다 줄의 방향이 다르다 — 층마다 밝은 가로줄인 덩어리와 밝은 세로 핀인 덩어리가 번갈아 놓인다
                       (삼성전자 동 서쪽 면: 아래는 세로 핀, 틈 위는 가로줄. 거리뷰). 윗덩어리는 한쪽으로 밀려 나와 있고 그 밑 모퉁이에 여러 층 높이의 짙은 틈이 있다. 꼭대기에는 짙은 설비 띠.
                       삼성전자 동의 북서 모퉁이 틈과 북쪽 낮은 별동(짙은 유리 + 밝은 가로 루버)은 거리뷰에서 본 자리이고, 나머지 동의 덩어리 경계 높이·밀린 방향(2~2.5 m)·틈의 자리는 같은 꼴을 어림해 둔 것이다
                       (prep_extra.py 가 전자 동을 타워와 별동으로 나누고 생명 동의 윤곽을 고친다).
  메리츠타워: 옥상을 두른 비스듬한 금속 틀(북서 변이 높고 남동 변이 낮다. 위성 화면에서는 헬리패드를 두른 흰 테로 보인다). 높이 12 m 는 어림.
  강남역 지하쇼핑센터: 지하 상가(OSM location=underground)가 69 m 건물로 서 있던 것을 뺀다.
  GS타워: 긴 면은 밝은 은회색 격자(lm_build.py 의 LMC), 서쪽 끝면은 짙은 반사 유리에 검은 세로 줄 하나와 꼭대기의 계단꼴 검은 홈, 'GS타워' 글자(일반 글꼴).
"""
cmb = MB(); _VOID, _SOF = mat_flat('#222932'), mat_flat('#dfe8f0')
def _vtx(g, dx, dy): return np.array(max(g.exterior.coords[:-1], key=lambda p: p[0] * dx + p[1] * dy)[:2])
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
    """삼성 서초사옥 한 동. cfg['vols'] = 아래부터 (윗높이 ÷ 전체 높이, 줄 방향 'h'|'v', 밀림 (동, 북) m), cfg['voids'] = (모퉁이 방향, 폭 m, 아래 ÷ H, 위 ÷ H, 덩어리 순번)."""
    poly = orient(P(b['rings']), 1.0); H = b['h']; mb = MB(); LB = cfg.get('lobby', 10.0); z0 = LB; gs = []
    _lobby(mb, poly, LB, cfg['glass'], cfg['spc'], cfg['line'])
    for f1, kind, (dx, dy) in cfg['vols']:
        g = orient(shapely.affinity.translate(poly, dx, dy), 1.0); z1 = H * f1; m, tw, th = _sstex(kind, cfg['glass'] if kind == 'h' else shade(cfg['glass'], .9), cfg['fin'])
        skin(mb, g, z0, lambda x, y, z1=z1: z1, m, tw, th); capf(mb, g, lambda x, y, z1=z1: z1, mat_flat('#aeb8c2')); gs.append(g); z0 = z1
    for (dx, dy), w, f0, f1, k in cfg['voids']:   # 모퉁이를 감싸는 짙은 틈과, 그 위로 내민 윗덩어리의 밝은 밑단
        g = gs[k]; dv = _vtx(g, dx, dy) - np.array(g.centroid.coords[0]); wall_strip(mb, g, dv, H * f0, H * f1, _VOID, w=w, off=.3); wall_strip(mb, g, dv, H * f1, H * f1 + .6, _SOF, w=w + 1.2, off=.5)
    g = gs[-1]; cb = orient(g.buffer(.3, join_style=2), 1.0); skin(mb, cb, H - 6.0, lambda x, y: H + .2, mat_flat('#34404e'), 1, 1)   # 꼭대기의 짙은 설비 띠
    _parapet(mb, g, H, '#c3d0dc'); c, ax_, Lx, Ly, _ = mrr_axes(g); core = g.buffer(-max(3.0, .26 * Ly), join_style=2); up_ = None
    if core.geom_type == 'Polygon' and core.area > 15: skin(mb, orient(core, 1.0), H, lambda x, y: H + 4.5, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: H + 4.5, mat_flat('#8c8e90')); up_ = (core, H + 4.5)
    roof_std(mb, g, H, up_[0] if up_ else None, up_[1] if up_ else H, False, b['seed'])
    inn = g.buffer(-1.5, join_style=2); inn = inn.difference(up_[0].buffer(.05)) if up_ else inn
    for q in parts(inn):
        if q.area > 6: capf(mb, orient(q, 1.0), lambda x, y: H + .09, mat_flat(cfg['deck']))
    toonify(mb.build('b%d' % idx, idx))
_SS = dict(glass='#5f8fca', fin='#c6d9ee', line='#3f6aa3', spc='#c3d0dc', lobby=10.0, deck='#c9cbcc')
LMC['samsung_e'] = dict(_SS, vols=((.62, 'v', (0, 0)), (1.0, 'h', (-2.0, 1.5))), voids=(((-1, .6), 46, .62, .72, 1), ((1, 1), 40, .24, .31, 0)))   # 삼성전자: 북서 모퉁이 높은 틈(거리뷰), 북동 모퉁이 낮은 틈
LMC['samsung_l'] = dict(_SS, vols=((.50, 'h', (0, 0)), (1.0, 'v', (-2.5, 0))), voids=(((0, 1), 40, .50, .58, 1), ((0, -1), 40, .74, .82, 1)))     # 삼성생명(어림)
LMC['samsung_c'] = dict(_SS, vols=((.42, 'v', (0, 0)), (1.0, 'h', (2.5, 0))), voids=(((-1, 0), 36, .42, .50, 1), ((1, 0), 36, .72, .80, 1)))      # 삼성화재(어림)
LMB.update(samsung_e=samsung, samsung_c=samsung, samsung_l=samsung)
def samsung_annex(b, idx):   # 삼성전자 동 북쪽의 낮은 별동
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
