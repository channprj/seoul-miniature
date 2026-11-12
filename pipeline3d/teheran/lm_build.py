# 테헤란로 지역 빌더. ../yeouido/gen_area.py 가 여의도 lm_build.py 다음에 exec 로 읽는다(같은 전역: MB, mat_flat, grid_tex, gtower, crystal, toonify, LMC, LMB, LMN …).
# 랜드마크의 색·꼭대기 형태는 기억에 의존한 추정이다(사진 대조를 하지 않았다). 높이·윤곽은 OSM. 글자·로고는 넣지 않는다.
KBSF.clear(); LMC.clear(); LMB.clear(); LMN.clear()   # 여의도 전용 표(건물 순번·이름)를 비운다

# ---------------- 격자 유리 타워 설정(gtower / crystal) ----------------
LMC.update({
    'wework': dict(glass='#6f8ea6', line='#4d6478', flh=4.0, bay=1.5, sp=.26, spc='#dfe3e4', lobby=7.0, kit=2),             # 위워크타워(테헤란로 427): 청회색 유리 + 밝은 층 띠
    'trade': dict(glass='#6d93b6', line='#47637f', flh=4.1, bay=1.5, sp=.30, spc='#3f5873', lobby=9.0, kit=1),               # 트레이드타워: 푸른 반사 유리 + 짙은 층 띠. 계단꼴 윤곽은 OSM 파트 그대로
    'asem': dict(glass='#5f8fbd', line='#3f6690', flh=4.1, bay=1.5, sp=.22, lobby=9.0, crownband=3.0, kit=3),
    'parnas': dict(glass='#93a6b3', line='#66788a', flh=4.2, bay=1.2, sp=.12, lobby=10.0, kit=2),
    'gfc': dict(glass='#577785', line='#3a5560', flh=4.3, bay=1.5, sp=.26, spc='#8b9ba0', lobby=10.0, crownband=4.0, kit=4),  # 강남파이낸스센터: 짙은 청록 유리
    'db': dict(glass='#7fa9b8', line='#56808f', flh=4.2, rise=14, sdir=(0.4, 0.9), facets=[(0.8, 0.6, .35, 9.0), (-0.75, -0.66, .55, 7.0)]),   # DB금융센터: 접힌 유리 결정
    'posco_e': dict(glass='#6fa4a6', line='#4a7b7e', flh=4.1, bay=1.5, sp=.30, spc='#cfd6d6', lobby=9.0, kit=3),             # 포스코센터: 청록 유리 + 은색 띠(두 동)
    'posco_w': dict(glass='#6fa4a6', line='#4a7b7e', flh=4.1, bay=1.5, sp=.30, spc='#cfd6d6', lobby=9.0, kit=3),
    'samsung_e': dict(glass='#7f9db6', line='#58758e', flh=4.2, bay=1.5, sp=.34, spc='#e0e4e6', lobby=10.0, kit=4),          # 삼성 서초사옥 세 동: 푸른 유리 + 흰 가로 띠
    'samsung_c': dict(glass='#7f9db6', line='#58758e', flh=4.2, bay=1.5, sp=.34, spc='#e0e4e6', lobby=10.0, kit=3),
    'samsung_l': dict(glass='#7f9db6', line='#58758e', flh=4.2, bay=1.5, sp=.34, spc='#e0e4e6', lobby=10.0, kit=2),
    'cf_e': dict(glass='#7c97ac', line='#566f84', flh=4.3, bay=1.5, sp=.18, lobby=10.0, kit=3),                               # 센터필드 두 동
    'cf_w': dict(glass='#7c97ac', line='#566f84', flh=4.3, bay=1.5, sp=.18, lobby=10.0, kit=3),
    'gs': dict(glass='#9fb2be', line='#73858f', flh=4.2, bay=1.5, sp=.40, spc='#d6dbde', lobby=10.0, crownband=3.0, kit=3),  # GS타워: 스테인리스 띠
    'meritz': dict(glass='#6f8fae', line='#4d6b88', flh=4.2, bay=1.5, sp=.20, lobby=9.0, kit=2),
    'glass': dict(glass='#44627e', line='#2f465c', flh=3.7, bay=1.5, sp=.16, lobby=8.0, kit=2),                              # 글라스타워: 짙은 청색 유리
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
    top = Polygon([p[:2] for p in R_[-1]]).buffer(0); capf(mb, top, lambda x, y: H, mat_flat('#9a9c9e')); _parapet(mb, orient(top, 1.0), H, cfg['spc']); roof_kit(mb, top, H, random.Random(b['seed']), 3)
    toonify(mb.build('gt%d' % idx, idx))

def coex(b, idx, cfg):
    """코엑스 전시장: 넓고 낮은 유리·금속 상자, 밝은 지붕에 긴 천창 띠(지붕 형태는 단순화, 높이 28 m 는 추정)."""
    poly = orient(P(b['rings']), 1.0); h = 28.0; mb = MB()
    path, tw, th = grid_tex('coex', '#8fa6b4', '#5f7684', 3.0, 7.0, sp=.25, spc='#d9dcdc'); skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'gcoex'), tw, th)
    flat_roof(mb, poly, h, '#d9dcdc', '#c2c5c6'); c, ax_, Lx, Ly, _ = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); inn = poly.buffer(-8.0)
    for k in range(-3, 4):   # 천창 띠
        q = Polygon([tuple(c + ax_ * su * Lx * .42 + nv * (k * Ly * .12 + sv * 3.2)) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]).intersection(inn)
        for g in parts(q):
            if g.area > 30: g = orient(g, 1.0); skin(mb, g, h, lambda x, y: h + 1.6, mat_flat('#a9b4ba'), 1, 1); capf(mb, g, lambda x, y: h + 1.6, mat_flat('#8fb2c8'))
    roof_kit(mb, poly, h, random.Random(11), 10)
    toonify(mb.build('b%d' % idx, idx))

LMB.update({k: gtower for k in LMC}); LMB.update(db=crystal, gt=gt_wave, coex=coex)

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
SITEK = {'현대자동차 글로벌비즈니스센터': 'gbc', '영동대로복합환승센터': 'gtx'}
PITZ = -1.8   # 굴착 바닥 = gen_area 의 물 바닥 높이(지면 판이 이 높이에 깔려 있다). 실제 깊이(수십 m)는 버팀보로만 암시한다
CONC, CONC2, RUST, YEL = '#b9b6ad', '#cfccc3', '#9a5a3c', '#e9b52e'
def tcrane(mb, p, H, ang, jib=44.0, cj=13.0, col=YEL):
    """타워크레인: 격자 마스트 + 수평 지브 + 평형추. 부재는 그림에서 보이게 굵게 과장했다."""
    m, dk = mat_flat(col), mat_flat(shade(col, .72)); x, y = p; s = 1.0; d = np.array([math.cos(ang), math.sin(ang)]); nv = np.array([-d[1], d[0]])
    mb.box((x, y, 0), 2.2, 2.2, .7, mat_flat('#9a9a94'))
    for k in range(int(H // 3)):
        z0, z1 = k * 3.0, k * 3.0 + 3.0; cs = [(x + sx * s, y + sy * s) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for j in range(4): beam(mb, (*cs[j], z0), (*cs[j], z1), .3, m); beam(mb, (*cs[j], z0), (*cs[(j + 1) % 4], z1), .16, m)
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
        g = orient(g, 1.0); skin(mb, g, 0.0, lambda x, y: 3.2, mat_flat('#eceae4'), 1, 1); skin(mb, orient(g.buffer(.06), 1.0), 2.2, lambda x, y: 2.8, mat_flat(stripe), 1, 1)
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
    for q, nfl in cores: p_ = (q[0] + 13.0, q[1] + 12.0); tcrane(mb, p_, max(36.0, nfl * 4.2 + 34.0), rnd.uniform(0, 6.28), jib=rnd.choice([40.0, 46.0, 52.0]))
    if kind == 'gtx':
        for q in _spots(ring, 3, rnd, 9.0): tcrane(mb, q, rnd.choice([39.0, 45.0]), rnd.uniform(0, 6.28), jib=38.0, col='#d9482e')
        for ln, r in _DRV:   # 차로 옆 플라스틱 방호벽(주황·흰색 번갈아)
            if r['cls'] != 'major' or not ln.intersects(poly): continue
            for sgn in (1, -1):
                for o in offs(ln, sgn * (r['w'] / 2 + 1.0)):
                    o = o.intersection(poly)
                    for q in ([o] if o.geom_type == 'LineString' else [x for x in getattr(o, 'geoms', []) if x.geom_type == 'LineString']):
                        for i_, s_ in enumerate(np.arange(0, q.length, 2.4)): p_ = q.interpolate(float(s_)); mb.box((p_.x, p_.y, 0), .5, .25, .9, mat_flat('#f08a24' if i_ % 2 else '#f3f1ea'))
    if mb.f: mb.build('site%d' % _k, 9700 + _k); META[9700 + _k] = 'landmark:site_' + kind
if _pits: WATERc = unary_union([WATERc] + _pits)   # 굴착 자리는 지면 판에서 도려낸다(gen_area 가 물가처럼 5.5 m 비탈을 두른다). 텍스처는 그대로 흙색
