# -*- coding: utf-8 -*-
"""랜드마크 타워에 덧붙이는 형태(lm_build.py 가 parnas.py 다음에 exec 한다). 네이버 지도 거리뷰와 위성 화면을 2026-11-13 에 눈으로 보고 옮겼다.
  삼성 서초사옥 세 동: 어긋나게 쌓은 유리 상자 사이의 짙은 틈(여러 층 높이, 모퉁이를 감쌈). 삼성전자 동의 북서 모퉁이 틈과 북쪽 낮은 별동(짙은 유리 + 밝은 가로 루버)은 거리뷰에서 본 자리이고,
                       나머지 틈의 모퉁이·높이는 같은 꼴을 어림해 둔 것이다(prep_extra.py 가 전자 동을 타워와 별동으로 나누고 생명 동의 윤곽을 고친다).
  메리츠타워: 옥상을 두른 비스듬한 금속 틀(북서 변이 높고 남동 변이 낮다. 위성 화면에서는 헬리패드를 두른 흰 테로 보인다). 높이 12 m 는 어림.
  강남역 지하쇼핑센터: 지하 상가(OSM location=underground)가 69 m 건물로 서 있던 것을 뺀다.
  GS타워: 긴 면은 밝은 은회색 격자(lm_build.py 의 LMC), 서쪽 끝면은 짙은 반사 유리에 검은 세로 줄 하나와 꼭대기의 계단꼴 검은 홈, 'GS타워' 글자(일반 글꼴).
"""
cmb = MB(); _VOID, _SOF = mat_flat('#222932'), mat_flat('#e3e9ec')
def _vtx(g, dx, dy): return np.array(max(g.exterior.coords[:-1], key=lambda p: p[0] * dx + p[1] * dy)[:2])
def _void(g, corner, w, z0, z1):
    """모퉁이를 감싸는 짙은 틈과, 그 위로 내민 윗덩어리의 밝은 밑단."""
    dv = corner - np.array(g.centroid.coords[0]); wall_strip(cmb, g, dv, z0, z1, _VOID, w=w, off=.3); wall_strip(cmb, g, dv, z1, z1 + .6, _SOF, w=w + 1.2, off=.5)
def samsung_annex(b, idx):   # 삼성전자 동 북쪽의 낮은 별동
    ltower(b, idx, dict(glass='#3d4852', line='#2a3239', flh=4.2, bay=1.5, sp=.5, spc='#96a0a8', lobby=8.0, kit=2, heli=False, deck='#6f8f6a'))
SPECIAL['r8311185n'] = samsung_annex
SPECIAL['w305923846'] = lambda b, idx: None   # 강남역 지하쇼핑센터: OSM 에 location=underground 로 올라 있는 지하 상가라 지상에는 아무것도 세우지 않는다(장면의 건물 순번이 밀리지 않게 항목은 그대로 둔다)
for _o, _vs in (('r8311185', (((-1, .6), 46, .62, .72), ((1, 1), 40, .24, .31))),          # 삼성전자: 북서 모퉁이 높은 틈(거리뷰), 북동 모퉁이 낮은 틈
                ('w504227059', (((0, 1), 40, .50, .58), ((0, -1), 40, .74, .82))),         # 삼성생명(어림)
                ('r8311184', (((-1, 0), 36, .42, .50), ((1, 0), 36, .72, .80)))):          # 삼성화재(어림)
    _b, _g = _bp(_o)
    if _b:
        for (dx, dy), w, f0, f1 in _vs: _void(_g, _vtx(_g, dx, dy), w, _b['h'] * f0, _b['h'] * f1)
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
