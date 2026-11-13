# 테헤란로 지역 빌더. ../yeouido/gen_area.py 가 여의도 lm_build.py 다음에 exec 로 읽는다(같은 전역: MB, mat_flat, grid_tex, gtower, crystal, toonify, LMC, LMB, LMN …).
# 높이·윤곽은 OSM. 색·입면 구성은 네이버 지도 거리뷰를 눈으로 보고 맞췄다(2026-11-12: 위워크타워, 트레이드타워, 아셈타워, 코엑스, 파르나스타워, 글라스타워, DB금융센터, 강남파이낸스센터, 포스코센터, GT타워, 센터필드, GS타워, 삼성 서초사옥).
# 옥상은 네이버 지도 위성 사진과 대조했다(2026-11-13: 헬리패드 유무와 바닥 색, 강남파이낸스센터의 층층이 물러나는 꼭대기, 센터필드의 태양광 판, 메리츠타워·트레이드타워의 초록 바닥 — detail.py 의 ltower). 설비의 정확한 자리는 맞추지 않았다. 사진은 저장소에 넣지 않았다. 간판 글자는 거리뷰에서 읽은 것만 signs.py 에서 붙인다(위워크타워는 아래 wework()).
# 삼성역 광장(원형 광장·내리막 계단·조형탑·화단·공사 야적장)은 plaza_samseong.py 에 따로 있고, 이 파일 끝에서 읽는다.
KBSF.clear(); LMC.clear(); LMB.clear(); LMN.clear()   # 여의도 전용 표(건물 순번·이름)를 비운다

# ---------------- 격자 유리 타워 설정(gtower / crystal) ----------------
LMC.update({
    'wework': dict(glass='#6fa0a8', line='#4a747c', flh=4.0, bay=1.5, sp=.16),                                              # 위워크타워(테헤란로 427): 석재 저층부 + 청록 유리 타워(아래 wework())
    'trade': dict(glass='#64798f', line='#3c4b5c', flh=4.1, bay=1.2, sp=.20, spc='#44566a', lobby=9.0, kit=1, heli=('#4f9a78', '#f6f6f1'), deck='#d9dcdc'),               # 트레이드타워: 회청색 반사 유리, 세로 결. 계단꼴 윤곽은 OSM 파트 그대로
    'asem': dict(glass='#6c8197', line='#44586c', flh=4.1, bay=1.5, sp=.36, spc='#aeb8c1', lobby=9.0, crownband=3.0, kit=3, heli=('#4a4f55', '#f1f1ec'), deck='#4f555b'),  # 아셈타워: 청회색 유리 + 밝은 가로 띠
    'parnas': dict(glass='#6d7f90', line='#44535f', flh=4.2, bay=1.5, sp=.20, spc='#9ba8b3', lobby=10.0, kit=2, heli=('#3f464d', '#f1f1ec'), deck='#3f464d'),             # 파르나스타워: 짙은 청회색 유리
    'gfc': dict(glass='#5d8fbf', line='#3d6791', flh=4.3, bay=1.5, sp=.16, lobby=10.0, kit=4, heli=False, tiers=3, deck='#8f9296'),                # 강남파이낸스센터: 맑은 파란 유리 커튼월
    'db': dict(glass='#5c7389', line='#3b4e60', flh=4.2, rise=14, sdir=(0.4, 0.9), facets=[(0.8, 0.6, .35, 9.0), (-0.75, -0.66, .55, 7.0)]),   # DB금융센터: 짙은 청회색 유리, 접힌 면(면의 방향·깊이는 추정)
    'posco_e': dict(glass='#6fa4a6', line='#4a7b7e', flh=4.1, bay=1.5, sp=.30, spc='#cfd6d6', lobby=9.0, kit=3),             # 포스코센터: 청록 유리 + 은색 띠(두 동)
    'posco_w': dict(glass='#6fa4a6', line='#4a7b7e', flh=4.1, bay=1.5, sp=.30, spc='#cfd6d6', lobby=9.0, kit=3),
    'samsung_e': dict(glass='#a3bdd2', line='#7896ae', flh=4.2, bay=1.5, sp=.34, spc='#e6ecef', lobby=10.0, kit=4, heli=False, deck='#c9cbcc'),          # 삼성 서초사옥 세 동: 밝은 하늘빛 유리 + 흰 가로 띠
    'samsung_c': dict(glass='#a3bdd2', line='#7896ae', flh=4.2, bay=1.5, sp=.34, spc='#e6ecef', lobby=10.0, kit=3, heli=False, deck='#c9cbcc'),
    'samsung_l': dict(glass='#a3bdd2', line='#7896ae', flh=4.2, bay=1.5, sp=.34, spc='#e6ecef', lobby=10.0, kit=2, heli=False, deck='#c9cbcc'),
    'cf_e': dict(glass='#5d7186', line='#2f3b47', flh=4.3, bay=1.0, sp=.10, lobby=10.0, kit=3, heli=False, deck='#d0d2d3', solar=True),                               # 센터필드 두 동: 짙은 청회색 유리, 촘촘한 세로 멀리언
    'cf_w': dict(glass='#5d7186', line='#2f3b47', flh=4.3, bay=1.0, sp=.10, lobby=10.0, kit=3, heli=False, deck='#d0d2d3', solar=True),
    'gs': dict(glass='#4b5661', line='#2c343c', flh=4.2, bay=1.5, sp=.20, spc='#98a1a8', lobby=10.0, crownband=3.0, kit=3),  # GS타워: 짙은 회색 반사 유리 + 금속 띠
    'meritz': dict(glass='#6f8fae', line='#4d6b88', flh=4.2, bay=1.5, sp=.20, lobby=9.0, kit=2, heli=('#4f9a78', '#f6f6f1'), heliflat=True, deck='#4f9a78'),
    'glass': dict(glass='#768a9b', line='#4d5f6e', flh=3.7, bay=1.5, sp=.30, spc='#aab3ba', lobby=8.0, kit=2, heli=('#8d949c', '#f1f1ec'), deck='#9a9c9e'),               # 글라스타워: 둥근 평면의 회청색 유리 + 가로 띠
    'gt': dict(glass='#6f9cc0', line='#4c7396', flh=4.4, bay=1.6, sp=.14, spc='#e9eef0'),                                    # GT타워: 물결치는 유리면
    'coex': dict(),
})

def gt_wave(b, idx, cfg):
    """GT타워: 평면이 높이에 따라 부풀었다 줄어드는 물결 유리면(긴 축·짧은 축의 위상이 다르다). 물결의 크기·주기는 추정."""
    poly = orient(P(b['rings']), 1.0); c, ax_, Lx, Ly, _ = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); H = b['h']; mb = MB()
    key = f"gt_{cfg['glass']}"; path, tw, th = grid_tex(key, cfg['glass'], cfg['line'], cfg['bay'], cfg['flh'], sp=cfg['sp'], spc=cfg['spc']); gm = mat_tex(path, 'g' + key)
    loc = [((p[0] - c[0]) * ax_[0] + (p[1] - c[1]) * ax_[1], (p[0] - c[0]) * nv[0] + (p[1] - c[1]) * nv[1]) for p in list(poly.exterior.coords)[:-1]]
    def ring(z):
        t = 2 * math.pi * z / H; su, sv = 1 + .05 * math.sin(t + 2.2), 1 + .11 * math.sin(t * 1.5 + .4)
        return [(c[0] + ax_[0] * u * su + nv[0] * v * sv, c[1] + ax_[1] * u * su + nv[1] * v * sv, z) for u, v in loc]
    zs = list(np.arange(0, H, cfg['flh'] / 2)) + [H]; R_ = [ring(z) for z in zs]; n = len(loc)
    s0 = np.cumsum([0] + [math.hypot(R_[0][(i + 1) % n][0] - R_[0][i][0], R_[0][(i + 1) % n][1] - R_[0][i][1]) for i in range(n)])
    for k in range(len(zs) - 1):
        for i in range(n):
            a, q, q2, a2 = R_[k][i], R_[k][(i + 1) % n], R_[k + 1][(i + 1) % n], R_[k + 1][i]
            mb.face([a, q, q2, a2], gm, [(s0[i] / tw, a[2] / th), (s0[i + 1] / tw, q[2] / th), (s0[i + 1] / tw, q2[2] / th), (s0[i] / tw, a2[2] / th)])
    top = Polygon([p[:2] for p in R_[-1]]).buffer(0); capf(mb, top, lambda x, y: H, mat_flat('#9a9c9e')); _parapet(mb, orient(top, 1.0), H, cfg['spc']); tc_, tax_, _tx, tLy_, _m = mrr_axes(top); capf(mb, top.buffer(-1.2), lambda x, y: H + .08, mat_flat('#c2c4c3')); mb.box((tc_[0], tc_[1], H), 9.0, 7.5, 3.2, mat_flat('#b9bcba'), math.atan2(tax_[1], tax_[0]), mat_flat('#c9cbc8')); helipad(mb, tc_, tax_, H + 3.2, 6.5, '#c9cbc8', '#ffffff', 'circle', .3)   # 위성 사진: 밝은 회색 바닥, 가운데 단 위의 밝은 헬리패드
    toonify(mb.build('gt%d' % idx, idx))

def coex(b, idx, cfg):
    """코엑스 전시장(거리뷰: 파란 반사 유리 벽): 넓고 낮은 유리 상자, 밝은 지붕에 긴 천창 띠(지붕 형태는 단순화, 높이 28 m 는 추정)."""
    poly = orient(P(b['rings']), 1.0); h = 28.0; mb = MB()
    path, tw, th = grid_tex('coex', '#5a86c2', '#3c5f96', 3.0, 7.0, sp=.18, spc='#c9d3dc'); skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'gcoex'), tw, th)
    flat_roof(mb, poly, h, '#d9dcdc', '#c2c5c6'); c, ax_, Lx, Ly, _ = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); inn = poly.buffer(-8.0)
    for k in range(-3, 4):   # 천창 띠
        q = Polygon([tuple(c + ax_ * su * Lx * .42 + nv * (k * Ly * .12 + sv * 3.2)) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]).intersection(inn)
        for g in parts(q):
            if g.area > 30: g = orient(g, 1.0); skin(mb, g, h, lambda x, y: h + 1.6, mat_flat('#a9b4ba'), 1, 1); capf(mb, g, lambda x, y: h + 1.6, mat_flat('#8fb2c8'))
    roof_kit(mb, poly, h, random.Random(11), 10)
    toonify(mb.build('b%d' % idx, idx))

def wework(b, idx, cfg):
    """위워크타워(네이버 거리뷰 대조, 2026-07 촬영분): 두 층 높이 회색 화강석 기단, 그 위 분홍빛 베이지 석재 저층부(층마다 네모난 녹색 유리 창 묶음), 저층부 위로 조금 물러난 타워.
    타워는 베이지 석재 띠와 파란 유리 띠가 층마다 번갈아 있고, 테헤란로 쪽 면 가운데에 세로 유리 줄이 꼭대기까지 오르며, 맨 위 네 층은 전면 유리다.
    그 꼭대기 가운데에 짙은 띠 + 흰 'wework' 간판이 달려 있다(사용자 요청으로 이 건물만 글자를 넣었다. 그림에서 읽히도록 실제보다 크게 과장).
    저층부 높이(전체의 약 40 %)·물러난 폭 2.2 m·간판 크기는 사진 비례로 잡은 추정."""
    poly = orient(P(b['rings']), 1.0); H = b['h']; hb, hp, hg = 8.4, round(H * .40 / 4.0) * 4.0 + .4, H - 16.0; mb = MB()
    skin(mb, poly, 0.0, lambda x, y: hb, mat_flat('#8e8a8c'), 1, 1)
    path, tw, th = finwall_tex('wework', '#d8c3b0', '#4f7f78', '#d8c3b0', bay=5.0, flh=4.0, finw=1.3); skin(mb, poly, hb, lambda x, y: hp, mat_tex(path, 'fin_' + path), tw, th)
    up = poly.buffer(-2.2, join_style=2); up = orient(up, 1.0) if up.geom_type == 'Polygon' and up.area > 120 else poly
    flat_roof(mb, poly, hp, '#d8c3b0', '#a9a69d')
    k1 = f"wwb_{cfg['glass']}"; gp, gw, gh = grid_tex(k1, cfg['glass'], cfg['line'], cfg['bay'], cfg['flh'], sp=.42, spc='#d9cbb8'); skin(mb, up, hp, lambda x, y: hg, mat_tex(gp, 'g' + k1), gw, gh)
    k2 = f"wwt_{cfg['glass']}"; gp, gw, gh = grid_tex(k2, cfg['glass'], cfg['line'], cfg['bay'], cfg['flh'], sp=.06); skin(mb, up, hg, lambda x, y: H, mat_tex(gp, 'g' + k2), gw, gh)
    capf(mb, up, lambda x, y: H, mat_flat('#9a9c9e')); _parapet(mb, up, H, shade(cfg['glass'], .8)); roof_kit(mb, up, H, random.Random(b['seed']), 2)
    c, ax_, Lx, Ly, _ = mrr_axes(up); nv = np.array([-ax_[1], ax_[0]])   # 테헤란로 쪽 면 찾기
    rd = [LineString(r['pts']) for r in S['roads'] if r['name'] == '테헤란로']; near = min(rd, key=lambda l: l.distance(Point(*c))); q = near.interpolate(near.project(Point(*c)))
    f = np.array([q.x, q.y]) - c; fd, half, wide = max(((ax_, Lx / 2, Ly / 2), (-ax_, Lx / 2, Ly / 2), (nv, Ly / 2, Lx / 2), (-nv, Ly / 2, Lx / 2)), key=lambda t: float(t[0] @ f))
    side = np.array([-fd[1], fd[0]]); fc = c + fd * (half - .4)
    obox(mb, fc, fd, 1.0, wide * .40, hp, H + .9, mat_flat(shade(cfg['glass'], .92)), mat_flat('#8d9296'))                              # 가운데 세로 유리 줄(0.6 m 돌출)
    for sv in (-1, 0, 1): obox(mb, fc + side * sv * wide * .40, fd, 1.08, .3, hp, H + .9, mat_flat('#34444f'))                           # 짙은 세로 기둥선
    sp_ = f'{TEXD}/wework_sign.png'
    if not os.path.exists(sp_):
        from PIL import ImageFont
        im = Image.new('RGB', (640, 150), '#27323b'); d = ImageDraw.Draw(im)
        try: fnt = ImageFont.truetype('/System/Library/Fonts/Supplemental/Georgia Bold.ttf', 128)
        except OSError: fnt = ImageFont.load_default(size=120)
        x0_, y0_, x1_, y1_ = d.textbbox((0, 0), 'wework', font=fnt); d.text(((640 - (x1_ - x0_)) / 2 - x0_, (150 - (y1_ - y0_)) / 2 - y0_), 'wework', font=fnt, fill='#ffffff'); im.save(sp_)
    sw, z0_, z1_ = wide * .80, H - 3.6, H + .9; p0, p1 = c + fd * (half + .72) - side * sw, c + fd * (half + .72) + side * sw
    mb.face([(*p0, z0_), (*p1, z0_), (*p1, z1_), (*p0, z1_)], mat_tex(sp_, 'wework_sign'), [(0, 0), (1, 0), (1, 1), (0, 1)])
    toonify(mb.build('b%d' % idx, idx))
LMB.update({k: gtower for k in LMC}); LMB.update(db=crystal, gt=gt_wave, coex=coex, wework=wework)

# ---------------- 기와지붕 전각(정자각·비각·재실, 봉은사 전각) ----------------
def tileroof(b, idx, wall='palace', roofc='#4d5258'):
    """기단 + 붉은 기둥 벽(또는 한옥 벽) + 기와지붕. 지붕은 처마선에서 안쪽으로 층층이 올려 임의 평면(丁 자 정자각 포함)에 맞춘 우진각 근사다."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 6: return
    mb = MB(); base, wh = .5, max(2.8, min(4.6, b['h'] * .45))
    pl = orient(poly.buffer(.9, join_style=2), 1.0); skin(mb, pl, 0.0, lambda x, y: base, mat_flat('#bdb3a0'), 1, 1); capf(mb, pl, lambda x, y: base, mat_flat('#cfc8b9'))
    walls(mb, poly, base, base + wh, wall, False, b['seed'], wh)
    half = mrr_axes(poly)[3] / 2 + 1.2; n = max(3, min(9, int(half / .55))); step = half / (n + .6); z = base + wh
    mb.face([(x, y, z) for x, y in list(orient(poly.buffer(1.2, join_style=2), -1.0).exterior.coords)[:-1]], mat_flat('#6a4a36'))   # 처마 밑
    for k in range(n):
        g = poly.buffer(1.2 - k * step, join_style=2)
        for q in parts(g):
            if q.area < .6: continue
            q = orient(q, 1.0); rise = .32 + .1 * k; skin(mb, q, z, lambda x, y: z + rise, mat_flat(shade(roofc, .82)), 1, 1); capf(mb, q, lambda x, y: z + rise, mat_flat(shade(roofc, 1 + .05 * (k % 2))))
        z += .32 + .1 * k
    mb.build('b%d' % idx, idx)
for _b in S['buildings']:
    _n = _b['name']
    if _n.endswith(('정자각', '비각', '수복방', '재실')): LMN[_n] = (tileroof, 'landmark:tomb_hall')
    elif _n.startswith('봉은사'): LMN[_n] = (lambda b, idx: tileroof(b, idx, 'palace' if b['area'] > 150 else 'hanok', '#555a60'), 'landmark:bongeunsa')

# ---------------- 선릉·정릉: 봉분 언덕, 곡장, 홍살문 ----------------
# 언덕은 지면 ID(1)로 둔다 → 분류 맵에서 그 자리의 녹지로 읽히고, 깊이 맵에는 실제 형상이 들어가 뒤쪽 사람을 가린다. 언덕 높이 9 m·모양은 추정.
HILLH = 9.0
def _cosfall(x, a, b_): return np.where(x <= a, 1.0, np.where(x >= b_, 0.0, .5 + .5 * np.cos(np.pi * (x - a) / (b_ - a))))
TOMBS = []
for _t in S.get('tombs', []):
    _c = np.array(_t['c']); _d = np.array(_t['toward']) - _c; _D = float(np.hypot(*_d)); _d /= _D
    TOMBS.append((_c, _d, np.array([-_d[1], _d[0]]), min(62.0, _D - 22.0)))
def hill_st(x, y, T):
    c, d, nrm, front = T; return (x - c[0]) * d[0] + (y - c[1]) * d[1], (x - c[0]) * nrm[0] + (y - c[1]) * nrm[1]
def hill_z(x, y):
    """(x, y) 의 언덕 높이(m). 봉분 둘레 평평한 능침 → 정자각 쪽으로 길게 내려가는 잔디 사면, 뒤·옆은 짧은 비탈."""
    z = np.zeros(np.shape(x))
    for T in TOMBS:
        s, t = hill_st(np.asarray(x, float), np.asarray(y, float), T)
        z = np.maximum(z, HILLH * _cosfall(s, 11.0, T[3]) * _cosfall(-s, 11.0, 30.0) * _cosfall(np.abs(t), 13.0, 34.0))
    return z
def _on_lawn(x, y): return any(-13 < s < T[3] and abs(t) < 15 for T in TOMBS for s, t in [hill_st(x, y, T)])
S['trees'] = [t for t in S['trees'] if not _on_lawn(t[0], t[1])]   # 능침 잔디 사면에는 나무가 없다
_tree0 = tree
def tree(i, x, y, r, mb):   # 언덕 비탈의 나무는 언덕 높이만큼 올린다
    z = float(hill_z(x, y)); n0 = len(mb.v); _tree0(i, x, y, r, mb)
    if z > .05: mb.v[n0:] = [(a, b_, c + z) for a, b_, c in mb.v[n0:]]
for _k, T in enumerate(TOMBS):
    c, d, nrm, front = T
    if not inwin(c, 16, 70): continue
    mb = MB(); gr = mat_flat('#93c268'); ss = np.arange(-31.0, front + 2.1, 2.0); ts = np.arange(-35.0, 35.1, 2.0)
    W3 = lambda s, t: (c[0] + d[0] * s + nrm[0] * t, c[1] + d[1] * s + nrm[1] * t)
    G = [[(*W3(s, t), float(hill_z(*W3(s, t)))) for t in ts] for s in ss]
    for i in range(len(ss) - 1):
        for j in range(len(ts) - 1):
            q = [G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]]
            if max(p[2] for p in q) > .02: mb.face(q, gr)
    prev = None   # 봉분: 반구에 가까운 잔디 봉우리(반지름 5.5 m, 높이 3.6 m) + 둘레 돌(병풍석)
    for a_ in range(0, 91, 15):
        r_, z_ = 5.5 * math.cos(math.radians(a_)), HILLH + .9 + 3.6 * math.sin(math.radians(a_))
        ring = [(c[0] + r_ * math.cos(2 * math.pi * k / 20), c[1] + r_ * math.sin(2 * math.pi * k / 20), z_) for k in range(20)]
        if prev:
            for k in range(20): mb.face([prev[k], prev[(k + 1) % 20], ring[(k + 1) % 20], ring[k]], mat_flat('#9bc970'))
        prev = ring
    mb.cyl((c[0], c[1], HILLH - .2), 5.9, 1.1, mat_flat('#c9c4b6'), mat_flat('#d6d1c4'), n=20)
    for k in range(12): a_ = 2 * math.pi * k / 12; mb.box((c[0] + 7.6 * math.cos(a_), c[1] + 7.6 * math.sin(a_), HILLH - .1), .22, .22, 1.3, mat_flat('#d9d5c9'), a_)   # 난간석 기둥
    a0 = math.atan2(-d[1], -d[0])   # 곡장: 봉분 뒤를 두른 낮은 담(기와 덮개)
    for k in range(-7, 7):
        a1, a2 = a0 + k * .2, a0 + (k + 1) * .2; p0, p1 = np.array([c[0] + 12 * math.cos(a1), c[1] + 12 * math.sin(a1)]), np.array([c[0] + 12 * math.cos(a2), c[1] + 12 * math.sin(a2)])
        beam(mb, (*p0, HILLH + .8), (*p1, HILLH + .8), .7, mat_flat('#d9c6a4'), 1.6); beam(mb, (*p0, HILLH + 1.75), (*p1, HILLH + 1.75), 1.1, mat_flat('#4d5258'), .3)
    for s_, t_ in ((9.5, -4.5), (9.5, 4.5), (15.0, -5.5), (15.0, 5.5), (15.0, -9.0), (15.0, 9.0)):   # 석물(문·무인석, 석마 자리)
        p_ = W3(s_, t_); mb.box((p_[0], p_[1], float(hill_z(*p_))), .45, .45, 2.2, mat_flat('#cfcabb'), math.atan2(d[1], d[0]))
    smooth_obj(mb.build('tomb%d' % _k, 1), 50.0)
for _k, g_ in enumerate(S.get('gates', [])):   # 홍살문: 붉은 두 기둥 + 가로대 두 줄 + 살
    x, y = g_['xy']
    if not inwin((x, y), 10, 6): continue
    mb = MB(); rm = mat_flat('#b5362a'); ax2 = np.array([-math.sin(g_['ang']), math.cos(g_['ang'])]); c_ = np.array([x, y])
    for sv in (-1, 1): p_ = c_ + ax2 * sv * 3.0; mb.cyl((p_[0], p_[1], 0), .28, 9.0, rm, n=8)
    for zb in (6.6, 7.7): beam(mb, (*(c_ - ax2 * 3.6), zb), (*(c_ + ax2 * 3.6), zb), .3, rm)
    for t_ in np.arange(-2.4, 2.5, .6): p_ = c_ + ax2 * t_; beam(mb, (*p_, 6.6), (*p_, 8.8), .14, rm)
    mb.build('gate%d' % _k, 9600 + _k); META[9600 + _k] = 'landmark:hongsalmun'

# ---------------- 공사 현장(OSM landuse=construction) ----------------
# 삼성역 일대: 현대차 GBC 신사옥 터(골조가 올라오는 코어 3기 + 타워크레인), 영동대로 복합환승센터(GTX: 도로 양옆 개착 구간의 버팀보·복공판·가림막).
# 그 밖의 공사 터는 가림막 + 장비, 넓으면 굴착 + 골조. 배치는 터 이름·자리로 고정한 난수다. 실제 공정·장비 배치와 다르다(연출).
SITEK = {'현대자동차 글로벌비즈니스센터': 'gbc', '영동대로복합환승센터': 'gtx', '삼성역 광장 공사 야적장': 'yard'}   # yard 는 plaza_samseong.py 가 따로 세운다
PITZ = -1.8   # 굴착 바닥 = gen_area 의 물 바닥 높이(지면 판이 이 높이에 깔려 있다). 실제 깊이(수십 m)는 버팀보로만 암시한다
CONC, CONC2, RUST, YEL = '#b9b6ad', '#cfccc3', '#9a5a3c', '#e9b52e'
def tcrane(mb, p, H, ang, jib=44.0, cj=13.0, col=YEL, z0=0.0):
    """타워크레인: 격자 마스트 + 수평 지브 + 평형추. 부재는 그림에서 보이게 굵게 과장했다."""
    m, dk = mat_flat(col), mat_flat(shade(col, .72)); x, y = p; s = 1.0; d = np.array([math.cos(ang), math.sin(ang)]); nv = np.array([-d[1], d[0]])
    mb.box((x, y, z0), 2.2, 2.2, .7, mat_flat('#9a9a94'))
    for k in range(int(z0 // 3), int(H // 3)):
        za_, z1 = max(z0, k * 3.0), k * 3.0 + 3.0; cs = [(x + sx * s, y + sy * s) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for j in range(4): beam(mb, (*cs[j], za_), (*cs[j], z1), .3, m); beam(mb, (*cs[j], za_), (*cs[(j + 1) % 4], z1), .16, m)
    zt = int(H // 3) * 3.0; mb.box((x, y, zt), 1.5, 1.5, 1.6, dk, ang); q = np.array([x, y]) + d * 1.9 - nv * 1.2; mb.box((q[0], q[1], zt + .2), .9, .8, 1.7, mat_flat('#e9e9e4'), ang)
    zb, za = zt + 1.9, zt + 3.3; P3 = lambda t, o, z: (x + d[0] * t + nv[0] * o, y + d[1] * t + nv[1] * o, z)
    for t in np.arange(0, jib, 3.0):
        t1 = min(jib, t + 3.0)
        for o in (-.7, .7): beam(mb, P3(t, o, zb), P3(t1, o, zb), .26, m); beam(mb, P3(t, o, zb), P3((t + t1) / 2, 0, za), .14, m); beam(mb, P3((t + t1) / 2, 0, za), P3(t1, o, zb), .14, m)
        beam(mb, P3(t, 0, za) if t else P3(1.5, 0, za), P3(t1 - 1.5 if t1 == jib else (t1 + min(jib, t1 + 3)) / 2, 0, za), .26, m)
    beam(mb, P3(0, 0, zb), P3(-cj, 0, zb), .9, m, .5); cw = P3(-cj + 1.6, 0, zb - 1.5); mb.box(cw, 1.6, 1.0, 1.5, mat_flat('#8d8f8c'), ang)
    ap = P3(0, 0, zt + 9.0)
    for o in (-.7, .7): beam(mb, P3(.8, o, zb), ap, .26, m); beam(mb, P3(-.8, o, zb), ap, .26, m)
    beam(mb, ap, P3(jib * .62, 0, za), .1, dk); beam(mb, ap, P3(-cj + .6, 0, zb + .3), .1, dk)
    hk = jib * .58; beam(mb, P3(hk, 0, zb - .3), P3(hk, 0, zt - 16.0), .08, mat_flat('#3a3a3c')); mb.box(P3(hk, 0, zt - 17.0), .5, .3, 1.0, mat_flat('#d9482e'), ang)
def excavator(mb, p, z, ang, col='#e8a020'):
    d = np.array([math.cos(ang), math.sin(ang)]); obox(mb, p, d, 2.2, 1.5, z, z + .9, mat_flat('#3c3d40')); obox(mb, p, d, 1.5, 1.25, z + .9, z + 2.5, mat_flat(col), mat_flat(shade(col, .8)))
    a, b_, c2 = np.array(p) + d * 1.2, np.array(p) + d * 4.6, np.array(p) + d * 6.6
    beam(mb, (*a, z + 2.0), (*b_, z + 4.8), .5, mat_flat(col)); beam(mb, (*b_, z + 4.8), (*c2, z + 1.5), .4, mat_flat(col)); obox(mb, c2, d, .6, .55, z + .6, z + 1.5, mat_flat('#3c3d40'))
def dumptruck(mb, p, z, ang, rnd):
    d = np.array([math.cos(ang), math.sin(ang)]); q = np.array(p)
    obox(mb, q + d * 2.9, d, 1.0, 1.2, z + .5, z + 3.0, mat_flat(rnd.choice(['#e9e9e4', '#2f5fa8', '#d9482e'])), mat_flat('#c9c9c4')); obox(mb, q - d * .7, d, 2.6, 1.25, z + 1.2, z + 2.9, mat_flat(rnd.choice(['#e8a020', '#6a7480', '#3d8f5a'])), mat_flat('#8b6f4e'))
    obox(mb, q, d, 3.9, 1.1, z, z + 1.0, mat_flat('#2c2d30'))
def containers(mb, p, ang, n, rnd, lv=2):
    d = np.array([math.cos(ang), math.sin(ang)]); nv = np.array([-d[1], d[0]])
    for k in range(n):
        for l in range(lv if rnd.random() < .7 else 1):
            c_ = rnd.choice(['#e9e9e4', '#e9e9e4', '#2f6fb3', '#3d8f5a', '#c8473c', '#d9a23a']); obox(mb, np.array(p) + nv * (k * 2.6), d, 3.05, 1.2, l * 2.6, l * 2.6 + 2.6, mat_flat(c_), mat_flat(shade(c_, .88)))
            obox(mb, np.array(p) + nv * (k * 2.6) + d * 3.06, d, .03, .5, l * 2.6 + .9, l * 2.6 + 2.0, mat_flat('#3f5567'))   # 창
def cframe(mb, c, ax, hx, hy, z0, nfl, rnd, fh=4.2, net=False):
    """철근콘크리트 골조: 기둥 격자 + 층 슬래브, 맨 위에 거푸집·철근. net = 두 면에 초록 수직 보호망."""
    nv = np.array([-ax[1], ax[0]]); c = np.array(c, float); cm, sm = mat_flat('#a9a69d'), mat_flat(CONC)
    nx, ny = max(2, int(round(2 * hx / 8)) + 1), max(2, int(round(2 * hy / 8)) + 1); zt = z0 + nfl * fh
    for i in range(nx):
        for j in range(ny):
            q = c + ax * (-hx + .5 + (2 * hx - 1) * i / (nx - 1)) + nv * (-hy + .5 + (2 * hy - 1) * j / (ny - 1)); obox(mb, q, ax, .45, .45, z0, zt, cm)
            for o in (-.25, .25): mb.box((q[0] + o, q[1] + o, zt), .07, .07, 1.5, mat_flat('#6b4a3a'))   # 기둥 철근
    for f in range(nfl): obox(mb, c, ax, hx, hy, z0 + (f + 1) * fh - .35, z0 + (f + 1) * fh, sm, mat_flat(CONC2))
    obox(mb, c - ax * hx * .35, ax, hx * .6, hy * .9, zt, zt + .12, mat_flat('#d1a94a'))   # 거푸집 합판
    for k in range(4): q = c + ax * rnd.uniform(.1, .8) * hx + nv * rnd.uniform(-.7, .7) * hy; obox(mb, q, ax, 2.4, .5, zt, zt + .35, mat_flat(RUST))   # 철근 다발
    if net:
        gm = mat_flat('#3f8f5a'); zn = max(z0 + fh, zt - fh)
        for a_, b_ in ((c + ax * (hx + .7) - nv * (hy + .7), c + ax * (hx + .7) + nv * (hy + .7)), (c + ax * (hx + .7) - nv * (hy + .7), c - ax * (hx + .7) - nv * (hy + .7))):
            mb.face([(*a_, z0), (*b_, z0), (*b_, zn), (*a_, zn)], gm)
def _spots(reg, n, rnd, r):
    out = []; reg = reg.buffer(-r)
    if reg.is_empty: return out
    x0, y0, x1, y1 = reg.bounds
    for _ in range(n * 40):
        if len(out) >= n: break
        q = Point(rnd.uniform(x0, x1), rnd.uniform(y0, y1))
        if reg.contains(q) and all(q.distance(Point(*o)) > 2.4 * r for o in out): out.append((q.x, q.y))
    return out
_DRV = [(LineString(r['pts']), r) for r in S['roads'] if r['cls'] in ('major', 'minor') and not r['tunnel'] and not r['bridge']]
_pits = []
for _k, _a in enumerate(AR.get('dirt', [])):
    poly = P(_a['rings'])
    if poly.area < 1500 or not poly.intersects(GBOX): continue
    if SITEK.get(_a['name']) == 'yard': continue
    kind = SITEK.get(_a['name'], 'lot'); cen = np.array(poly.centroid.coords[0]); rnd = random.Random(zlib.crc32(f"{_a['name']}{round(cen[0])}{round(cen[1])}".encode()))
    road = unary_union([ln.buffer(r['w'] / 2 + 2.5, cap_style=2) for ln, r in _DRV if ln.intersects(poly)] + [Point(0, 0).buffer(.01)])
    inner = poly.difference(road).buffer(-2.0).buffer(0); big = poly.area > 4000
    pit = inner.buffer(-(16.0 if kind == 'gbc' else 6.0 if kind == 'gtx' else 9.0)).buffer(0) if (big or kind != 'lot') else Polygon()
    pits = [g for g in parts(pit) if g.area > 500]; _pits += pits
    rad = max(Point(*cen).distance(Point(q)) for q in poly.exterior.coords) + 55
    if not inwin(cen, 110, rad): continue
    mb = MB(); stripe = {'gbc': '#3d8f5a', 'gtx': '#2f6fb3'}.get(kind, rnd.choice(['#d9822b', '#2f6fb3', '#3d8f5a']))
    for g in parts(inner):   # 가림막(흰 강판 + 색 띠)
        if g.area < 150: continue
        wall = g.difference(g.buffer(-.4, join_style=2))   # 3 m 가림벽(두께 0.4 m: 위에서도 흰 선으로 보인다) + 색 띠
        for w_ in parts(wall):
            w_ = orient(w_, 1.0); skin(mb, w_, 0.0, lambda x, y: 3.0, mat_flat('#eceae4'), 1, 1); capf(mb, w_, lambda x, y: 3.0, mat_flat('#f6f5f0'))
        skin(mb, orient(g.buffer(.05, join_style=2), 1.0), 1.9, lambda x, y: 2.5, mat_flat(stripe), 1, 1)
    cores = []
    for pi_, g in enumerate(pits):
        c_, ax_, Lx, Ly, _ = mrr_axes(g); nv = np.array([-ax_[1], ax_[0]]); fl = g.buffer(-5.5)
        for q in parts(fl): capf(mb, orient(q, 1.0), lambda x, y: PITZ + .03, mat_flat('#9c8563'))   # 굴착 바닥(짙은 흙)
        if kind == 'gbc' and pi_ == 0:   # 코어 3기(높이는 연출) + 둘레 골조
            for t_, nfl, net in ((-.30, 7, False), (.02, 4, True), (.32, 2, False)):
                q = c_ + ax_ * t_ * Lx + nv * rnd.uniform(-.08, .08) * Ly; cores.append((q, nfl))
                obox(mb, q, ax_, 9.0, 9.0, PITZ, (nfl + 2) * 4.2, mat_flat(CONC), mat_flat('#8f8c84')); cframe(mb, q, ax_, 21.0, 19.0, PITZ, nfl, rnd, net=net)
                for o in (-5.0, 0.0, 5.0): mb.box((q[0] + o * ax_[0], q[1] + o * ax_[1], (nfl + 2) * 4.2), .1, .1, 2.0, mat_flat('#6b4a3a'))
        elif kind == 'lot' and g.area > 2500:
            nfl = rnd.randrange(2, 7); cores.append((c_, nfl)); cframe(mb, c_, ax_, min(18.0, Lx * .28), min(14.0, Ly * .28), PITZ, nfl, rnd, net=rnd.random() < .6)
        keep = g.buffer(-1.0).difference(unary_union([Point(*q).buffer(31.0) for q, _n in cores] + [Point(0, 0).buffer(.01)]))
        for s_ in np.arange(-Lx / 2 + 3.5, Lx / 2, 7.0):   # 버팀보(짧은 축 방향, 7 m 간격) — 깊은 굴착 가시설
            seg = LineString([c_ + ax_ * s_ - nv * Ly, c_ + ax_ * s_ + nv * Ly]).intersection(keep)
            for q in ([seg] if seg.geom_type == 'LineString' else [x for x in getattr(seg, 'geoms', []) if x.geom_type == 'LineString']):
                if q.length > 4: a_, b_ = q.coords[0], q.coords[-1]; beam(mb, (*a_, -.35), (*b_, -.35), .7, mat_flat(RUST), .7)
        for s_ in np.arange(-Ly / 2 + 6.0, Ly / 2, 12.0):   # 띠장·중간 보(긴 축 방향)
            seg = LineString([c_ + nv * s_ - ax_ * Lx, c_ + nv * s_ + ax_ * Lx]).intersection(keep)
            for q in ([seg] if seg.geom_type == 'LineString' else [x for x in getattr(seg, 'geoms', []) if x.geom_type == 'LineString']):
                if q.length > 4: a_, b_ = q.coords[0], q.coords[-1]; beam(mb, (*a_, -.9), (*b_, -.9), .6, mat_flat(shade(RUST, .85)), .6)
        if kind == 'gtx':   # 복공판: 굴착 위를 덮은 강판 구간(구간마다 하나 걸러)
            for i_, s_ in enumerate(np.arange(-Lx / 2, Lx / 2, 14.0)):
                if i_ % 3 == 2: continue
                dk = Polygon([tuple(c_ + ax_ * (s_ + u) + nv * v * Ly) for u, v in ((0, -1), (7.0, -1), (7.0, 1), (0, 1))]).intersection(g.buffer(-.5))
                for q in parts(dk):
                    if q.area > 8: q = orient(q, 1.0); skin(mb, q, -.5, lambda x, y: .06, mat_flat('#5d6268'), 1, 1); capf(mb, q, lambda x, y: .06, mat_flat('#7d8187' if i_ % 2 else '#6f7379'))
        for q in _spots(keep.intersection(fl) if not fl.is_empty else Polygon(), max(1, min(6, int(g.area // 2500))), rnd, 5.0): excavator(mb, q, PITZ + .03, rnd.uniform(0, 6.28))
    ring = inner.difference(unary_union(pits + [Point(0, 0).buffer(.01)]).buffer(1.5)).buffer(-1.0)   # 지면 작업 띠: 사무실 컨테이너·자재·덤프트럭·장비
    for pg in parts(ring):
        if pg.area < 120: continue
        ang = math.atan2(*mrr_axes(pg)[1][::-1])
        for q in _spots(pg, max(1, min(10, int(pg.area // 900))), rnd, 6.0):
            k_ = rnd.random()
            if k_ < .34: containers(mb, q, ang + rnd.choice([0, math.pi / 2]), rnd.randrange(1, 4), rnd)
            elif k_ < .56: dumptruck(mb, q, 0.0, ang + rnd.choice([0, math.pi / 2, math.pi]), rnd)
            elif k_ < .74: excavator(mb, q, 0.0, rnd.uniform(0, 6.28))
            else:
                for j in range(rnd.randrange(2, 5)): obox(mb, np.array(q) + np.array([0, j * 1.1]), (math.cos(ang), math.sin(ang)), 3.2, .4, 0.0, .5, mat_flat(rnd.choice([RUST, '#6b4a3a', '#8d8f8c'])))
    ncr = 0   # 타워크레인: 골조마다 한 대, 굴착 구간에는 긴 축을 따라 약 110 m 마다, 그래도 없으면 터 가운데에 한 대
    for q, nfl in cores: p_ = (q[0] + 13.0, q[1] + 12.0); tcrane(mb, p_, max(36.0, nfl * 4.2 + 34.0), rnd.uniform(0, 6.28), jib=rnd.choice([40.0, 46.0, 52.0])); ncr += 1
    for g in pits:
        c_, ax_, Lx, Ly, _ = mrr_axes(g); fl = g.buffer(-3.0); n_ = int(Lx // 110) + (1 if kind == 'gtx' else 0)
        for i_ in range(n_):
            q = c_ + ax_ * ((i_ + .5) / n_ - .5) * Lx * .86
            if fl.contains(Point(*q)) and all(np.hypot(*(q - np.array(o))) > 34 for o, _n in cores): tcrane(mb, q, rnd.choice([39.0, 45.0, 51.0]), rnd.uniform(0, 6.28), jib=rnd.choice([36.0, 42.0]), col='#d9482e' if kind == 'gtx' else YEL, z0=PITZ); ncr += 1
    if not ncr:
        q = inner.buffer(-5.0).representative_point() if not inner.buffer(-5.0).is_empty else None
        if q is not None: tcrane(mb, (q.x, q.y), rnd.choice([30.0, 36.0]), rnd.uniform(0, 6.28), jib=30.0)
    if kind == 'gtx':
        for ln, r in _DRV:   # 차로 옆 플라스틱 방호벽(주황·흰색 번갈아)
            if r['cls'] != 'major' or not ln.intersects(poly): continue
            for sgn in (1, -1):
                for o in offs(ln, sgn * (r['w'] / 2 + 1.0)):
                    o = o.intersection(poly)
                    for q in ([o] if o.geom_type == 'LineString' else [x for x in getattr(o, 'geoms', []) if x.geom_type == 'LineString']):
                        for i_, s_ in enumerate(np.arange(0, q.length, 2.4)): p_ = q.interpolate(float(s_)); mb.box((p_.x, p_.y, 0), .5, .25, .9, mat_flat('#f08a24' if i_ % 2 else '#f3f1ea'))
    if mb.f: mb.build('site%d' % _k, 9700 + _k); META[9700 + _k] = 'landmark:site_' + kind
exec(compile(open(AREA + '/signs.py', encoding='utf-8').read(), AREA + '/signs.py', 'exec'))   # 랜드마크 간판·전광판
exec(compile(open(AREA + '/detail.py', encoding='utf-8').read(), AREA + '/detail.py', 'exec'))   # 일반 건물 세부(빌라·주택, 아파트 동과 단지, 일반 타워, 포스코센터)
exec(compile(open(AREA + '/plaza_samseong.py', encoding='utf-8').read(), AREA + '/plaza_samseong.py', 'exec'))   # 삼성역 광장(내리막 계단 자리는 _pits 에 더한다)
if _pits: WATERc = unary_union([WATERc] + _pits)   # 굴착 자리는 지면 판에서 도려낸다(gen_area 가 물가처럼 5.5 m 비탈을 두른다). 텍스처는 그대로 흙색
