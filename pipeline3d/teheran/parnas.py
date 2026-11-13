# 그랜드 인터컨티넨탈 서울 파르나스의 테헤란로 쪽 현관과 앞마당, 파르나스타워 모서리의 세로 전광판. lm_build.py 끝에서 exec 로 읽는다(detail.py·signs.py 뒤).
# 네이버 지도 거리뷰(2026-07 촬영분: 테헤란로 건너편, 동·서쪽 사거리)와 위성·일반 지도 화면을 보고 만들었다. 자리(진입 차로·로터리·정원·포장)는 prep_extra.py 가 장면 자료에 넣는다.
#   호텔: 은청색 유리 판상형(detail.py 의 TOWER_STYLE). 현관동: 2층 높이의 짙은 브론즈색 석재·유리 상자, 세로 금속 핀, 넓고 얇은 캐노피와 기둥, 캐노피 띠의 금색 글자, 그 위의 금색 표장.
#   앞마당: 테헤란로를 따라 소나무·활엽수와 다듬은 생울타리, 차 서는 곳의 볼라드와 화분, 로터리 가운데의 조경, 가로등.
#   깃대 줄과 유리 원형 지붕은 plaza_samseong.py 에 이미 있다(같은 거리뷰에서 본 것).
#   파르나스타워: 테헤란로 쪽 서쪽 모서리의 세로 전광판(화면은 광고가 아니라 색 무늬).
# 추정·단순화: 현관동·캐노피의 치수(폭 46 m, 깊이 9 m, 캐노피 34 × 13 m), 볼라드의 수와 간격, 조경 배치. 글자는 그림에서 보이도록 실제보다 크게 잡았다.
PNS = S.get('parnas')
if PNS and inwin(PNS['F'], 20, 120):
    F, d, e = (np.array(PNS[k], float) for k in ('F', 'd', 'e')); Dr = PNS['Dr']; Rc = np.array(PNS['Rc'], float); mb = MB(); Q = lambda u, v: F + e * u + d * v
    brz, brz2, gold = '#4a4038', '#3a322c', '#c9a24c'
    def lob(d_):   # 현관동 입면: 짙은 유리 + 브론즈 세로 핀, 아래는 밝은 로비 유리
        for x in range(0, 384, 24): d_.rectangle([x, 0, x + 23, 216], fill='#39424a'); d_.rectangle([x, 110, x + 23, 208], fill='#6f8794'); d_.rectangle([x, 0, x + 4, 216], fill=brz2)
        d_.rectangle([0, 100, 384, 108], fill=brz2); d_.rectangle([0, 208, 384, 216], fill='#2f2924')
    pav = orient(Polygon([tuple(Q(u, v)) for u, v in ((-23, -.5), (23, -.5), (23, 9), (-23, 9))]), 1.0)
    skin(mb, pav, 0.0, lambda x, y: 9.0, mat_tex(_png('parnas_lobby', 384, 216, brz, lob), 'parnas_lobby'), 16.0, 9.0); capf(mb, pav, lambda x, y: 9.0, mat_flat('#5a5048')); _parapet(mb, pav, 9.0, brz, .7)
    obox(mb, Q(0, 15.5), d, 6.5, 17.0, 5.6, 6.3, mat_flat(brz2), mat_flat('#5d534a'))                       # 캐노피(차 서는 곳을 덮는다)
    obox(mb, Q(0, 15.5), d, 5.6, 16.0, 5.45, 5.6, mat_flat('#e6d9b8'))                                      # 캐노피 밑면의 밝은 조명 판
    for u in (-15.5, -5.2, 5.2, 15.5):
        for v in (10.5, 20.5): q = Q(u, v); mb.box((q[0], q[1], 0), .35, .35, 5.6, mat_flat(brz), math.atan2(d[1], d[0]))
    pth, asp = sign_png('intercon', 'INTERCONTINENTAL', gold, brz2, SERIF, track=.2, pad=.2); hh = 1.5; w = min(30.0, hh * asp); m0 = Q(0, 22.05); a_, b_ = m0 + e * w / 2, m0 - e * w / 2   # 캐노피 앞 띠의 금색 글자(길 쪽에서 읽힌다)
    mb.face([(*a_, 6.3), (*b_, 6.3), (*b_, 6.3 + hh), (*a_, 6.3 + hh)], mat_tex(pth, 'sg_intercon'), [(0, 0), (1, 0), (1, 1), (0, 1)])
    q = Q(0, 9.1); mb.cyl((q[0], q[1], 9.9), 1.1, .5, mat_flat(gold), mat_flat('#e6c878'), n=16)             # 현관동 위의 금색 표장(원반)
    rnd = random.Random(1107)
    for u in np.arange(-33.0, 49.0, 3.2):   # 테헤란로를 따라 다듬은 생울타리 두 줄
        for v, hgt in ((Dr - 1.4, .9), (23.2, .7)):
            if abs(u) < 3 and v < 24: continue
            q = Q(u, v); obox(mb, q, e, 1.5, .55, 0.0, hgt + rnd.uniform(-.08, .08), mat_flat('#3f7d3a'), mat_flat('#4f8f3f'))
    for u in np.arange(-28.0, 30.0, 4.0):   # 차 서는 곳 가장자리의 볼라드와 화분
        q = Q(u, 21.6); mb.cyl((q[0], q[1], 0), .16, .85, mat_flat('#8a8d90'), n=8)
    for u in (-19.0, 19.0): q = Q(u, 11.2); mb.cyl((q[0], q[1], 0), .8, .6, mat_flat('#3a3d42'), mat_flat('#4f8f3f'), n=12)
    for a in np.arange(0, 6.28, .52): q = Rc + 3.9 * np.array([math.cos(a), math.sin(a)]); obox(mb, q, (-math.sin(a), math.cos(a)), .95, .45, 0.0, .7, mat_flat('#3f7d3a'), mat_flat('#4f8f3f'))   # 로터리 둘레 생울타리
    mb.cyl((Rc[0], Rc[1], 0), 5.3, .25, mat_flat('#bdb9b0'), mat_flat('#6aa84e'), n=24)
    for u, v in ((-36, 20), (-12, 26.5), (12, 26.5), (40, 20), (56, 8)):   # 가로등(기둥 + 팔)
        q = Q(u, v); mb.cyl((q[0], q[1], 0), .11, 8.0, mat_flat('#5d646b'), n=6); beam(mb, (*q, 8.0), (*(q + d * 1.6), 8.2), .14, mat_flat('#5d646b')); mb.box((q[0] + d[0] * 1.6, q[1] + d[1] * 1.6, 8.05), .35, .18, .14, mat_flat('#e9e6d6'))
    toonify(mb.build('parnas_court', 9790)); META[9790] = 'landmark:parnas_court'
    tb, tg = _bp('w927603580')   # 파르나스타워: 테헤란로 쪽 서쪽 모서리의 세로 전광판
    if tb:
        tc = np.array(tg.centroid.coords[0]); half = max(abs(float((np.array(q_) - tc) @ e)) for q_ in tg.exterior.coords); smb2 = MB(); o1 = tc - e * (half - 6.0)
        wall_strip(smb2, tg, d, 34.0, 96.0, mat_tex(screen_png('parnas_led', 96, 480, ['#e9d6e6', '#b98fc9', '#fdfdf3', '#7a5a9a', '#e6a8b8', '#3a3550'], 23), 'sc_parnas'), w=8.0, off=1.0, org=o1)
        wall_strip(smb2, tg, d, 33.4, 96.6, mat_flat('#22272b'), w=9.0, off=.75, org=o1)
        if smb2.f: toonify(smb2.build('parnas_led', 9791)); META[9791] = 'landmark:signs'

# ================= 현대백화점 무역센터점 =================
# 네이버 지도 거리뷰(2026-07: 테헤란로 건너편, 동·서쪽 모서리, 서쪽 골목)와 위성 화면을 보고 만들었다.
#   몸체: 창이 거의 없는 베이지색 석재 타일 상자. 벽에 짧고 짙은 가로 홈이 흩어져 있고, 아래 두 층은 짙은 갈색 화강석에 진열창.
#   테헤란로 쪽 면: 위쪽의 길고 얇은 띠창, 왼쪽 위의 짙은 'THE HYUNDAI'(signs.py), 가운데의 석재 틀 유리 현관과 캐노피, 벽면의 포스터 판, 동쪽 끝의 세로 전광판(signs.py).
#   옥상(위성): 가운데 남쪽의 하늘정원(잔디와 흰 파라솔 줄), 동쪽의 밝은 지붕 판과 태양광 띠, 북쪽의 냉각탑 두 줄, 서쪽의 설비·덕트, 남동 모서리의 옥탑.
# 추정·단순화: 높이 50 m(prep_extra.py), 띠창·현관·포스터의 치수와 자리, 가로 홈의 수, 옥상 구획의 크기. 포스터는 광고가 아니라 색 무늬다.
def hyundai_store(b, idx):
    poly = orient(P(b['rings']), 1.0); H = b['h']; mb = MB(); c, ax_, Lx, Ly, mc = mrr_axes(poly); c = np.array(mc).mean(axis=0); BH = 8.0; stone, base = '#b9a98c', '#6b584c'
    d = np.array(_toward_road(poly, '테헤란로'), float); d /= np.hypot(*d); e = np.array([-d[1], d[0]]); e = e if e[0] > 0 else -e
    He = max(abs(float((np.array(q) - c) @ e)) for q in poly.exterior.coords); Hd = max(abs(float((np.array(q) - c) @ d)) for q in poly.exterior.coords); Q = lambda u, v: c + e * u * He + d * v * Hd
    def tex(d_):   # 석재 타일(1.2 × 0.6 m 줄눈)과 짧고 짙은 가로 홈
        rr = random.Random(74013224)
        for y in range(0, 480, 15): d_.line([(0, y), (960, y)], fill='#ab9b7f')
        for x in range(0, 960, 30): d_.line([(x, 0), (x, 480)], fill='#b1a184')
        for _ in range(9): x, y, w = rr.randrange(0, 820), rr.randrange(30, 450), rr.randrange(70, 190); d_.rectangle([x, y, x + w, y + 7], fill='#3d362e')
    def btex(d_):  # 저층부: 짙은 화강석 + 진열창
        for x in range(0, 480, 60): d_.rectangle([x + 8, 70, x + 52, 150], fill='#39434b'); d_.rectangle([x + 8, 70, x + 52, 76], fill='#2a2420'); d_.rectangle([x + 12, 96, x + 30, 150], fill='#7f96a3')
        d_.rectangle([0, 0, 480, 10], fill='#57463c')
    skin(mb, poly, 0.0, lambda x, y: BH, mat_tex(_png('hd_base', 480, 160, base, btex), 'hd_base'), 24.0, BH); skin(mb, poly, BH, lambda x, y: H, mat_tex(_png('hd_stone', 960, 480, stone, tex), 'hd_stone'), 48.0, 24.0)
    cb = orient(poly.buffer(.25, join_style=2), 1.0); skin(mb, cb, BH - .5, lambda x, y: BH, mat_flat('#57463c'), 1, 1)   # 저층부 위의 돌림띠
    capf(mb, poly, lambda x, y: H, mat_flat('#6f665b')); _parapet(mb, poly, H, stone, 1.4)
    # 테헤란로 쪽 면
    wall_strip(mb, poly, d, H - 13.0, H - 10.6, mat_flat('#2f3840'), w=He * 1.05, off=.18, org=c + e * He * .12); wall_strip(mb, poly, d, H - 13.4, H - 10.2, mat_flat('#8a7d68'), w=He * 1.05 + .8, off=.1, org=c + e * He * .12)   # 긴 띠창과 틀
    wall_strip(mb, poly, d, 0.0, 12.5, mat_flat('#a3957c'), w=19.0, off=.9, org=c + e * He * .05); wall_strip(mb, poly, d, 0.6, 11.2, mat_flat('#6f8a99'), w=14.5, off=1.05, org=c + e * He * .05)                          # 석재 틀 유리 현관
    for z_ in (4.2, 7.8): wall_strip(mb, poly, d, z_, z_ + .25, mat_flat('#3a3f44'), w=14.5, off=1.1, org=c + e * He * .05)
    eo = c + e * He * .05; hh = LineString([eo, eo + d * 300]).intersection(poly.exterior); ent = np.array((hh if hh.geom_type == 'Point' else max(hh.geoms, key=lambda g: (g.x - eo[0]) * d[0] + (g.y - eo[1]) * d[1])).coords[0])
    obox(mb, ent + d * 2.6, d, 2.6, 9.0, 4.6, 5.0, mat_flat('#2f2a26'), mat_flat('#4a433c'))   # 현관 캐노피
    wall_strip(mb, poly, d, 17.0, 28.0, mat_tex(screen_png('hd_poster', 160, 200, ['#c9d6dc', '#8fb7d8', '#f3f0e6', '#d9c27a', '#7fa8c8', '#e6e2d6'], 31), 'sc_hd_poster'), w=9.5, off=.3, org=c - e * He * .42)                   # 벽면 포스터 판
    wall_strip(mb, poly, d, 16.5, 28.5, mat_flat('#8a7d68'), w=10.5, off=.2, org=c - e * He * .42)
    # 옥상
    inn = poly.buffer(-2.2, join_style=2); ok = lambda q, r=1.0: inn.contains(Point(*q).buffer(r)); ang = math.atan2(e[1], e[0])
    gd = Polygon([tuple(Q(u, v)) for u, v in ((-.42, .02), (.08, .02), (.08, .70), (-.42, .70))]).intersection(inn)                # 하늘정원
    for q in parts(gd): q = orient(q, 1.0); skin(mb, q, H, lambda x, y: H + .35, mat_flat('#8a7d68'), 1, 1); capf(mb, q, lambda x, y: H + .35, mat_flat('#5f8a4a'))
    for q in parts(gd.buffer(-4.0)): capf(mb, orient(q, 1.0), lambda x, y: H + .4, mat_flat('#74a358'))
    def parasol(q): mb.cyl((q[0], q[1], H + .35), .06, 2.3, mat_flat('#8d9296'), n=6); mb.cyl((q[0], q[1], H + 2.5), 1.7, .12, mat_flat('#f4f3ee'), mat_flat('#ffffff'), n=12)
    for v in np.linspace(.0, .62, 7):
        if ok(Q(.16, v), 1.8): parasol(Q(.16, v))
    for u, v in ((.42, .66), (.52, .64), (.62, .66), (.52, .74)):
        if ok(Q(u, v), 1.8): parasol(Q(u, v))
    ep = Polygon([tuple(Q(u, v)) for u, v in ((.30, -.62), (.94, -.62), (.94, .42), (.30, .42))]).intersection(inn)                # 동쪽의 밝은 지붕 판 + 태양광 띠
    for q in parts(ep): q = orient(q, 1.0); skin(mb, q, H, lambda x, y: H + 1.6, mat_flat('#b9bcba'), 1, 1); capf(mb, q, lambda x, y: H + 1.6, mat_flat('#d9dbd9'))
    for v in np.arange(-.56, .38, .058):
        for u in (.335, .41):
            if ep.buffer(-1.5).contains(Point(*Q(u, v))): obox(mb, Q(u, v), e, 2.3, 1.05, H + 1.62, H + 1.95, mat_flat('#2f4a78'), mat_flat('#3a5a92'))
    for k in range(9):                                                                                                               # 북쪽의 냉각탑 두 줄
        for v in (-.90, -.76):
            q = Q(-.50 + k * .115, v)
            if ok(q, 2.2): _cooler(mb, q, e, H + .05, 2.0, 2.6)
    rr = random.Random(7401)
    for v in np.arange(-.62, .0, .13):                                                                                               # 서쪽의 설비·덕트
        q = Q(-.72 + rr.uniform(-.06, .06), v)
        if ok(q, 3.2): obox(mb, q, e, rr.uniform(2.2, 4.0), rr.uniform(1.6, 2.6), H, H + rr.uniform(1.6, 3.0), mat_flat('#a9aaa8'), mat_flat('#c2c5c4'))
    for v in (-.5, -.2): beam(mb, (*Q(-.72, v), H + 1.2), (*Q(-.3, v), H + 1.2), .9, mat_flat('#c9cbc8'), .7)
    q = Q(.74, .72)
    if ok(q, 5.0): obox(mb, q, e, 6.0, 5.0, H, H + 4.2, mat_flat(stone), mat_flat('#a9aaa8'))                                        # 남동 모서리의 옥탑
    toonify(mb.build('b%d' % idx, idx))
SPECIAL = {'w74013224': hyundai_store}

# ================= 현대아이파크타워의 입면 조형 =================
# 네이버 지도 거리뷰(2026-07 촬영분, 영동대로 건너편 세 자리와 남·서쪽)를 보고 만들었다. 청회색 유리 상자의 영동대로 쪽 면에:
#   은회색 금속 원 테(입면 폭을 거의 다 차지하고 지붕선에 닿는다), 원의 왼쪽 아래를 채운 붉은 가는 가로줄 무늬, 아래쪽을 가로지르는 붉은 띠, 유리에서 튀어나온 붉은 세로 상자 여덟 개,
#   왼쪽 위의 짙은 붉은 상자와 흰 글자 'HDC', 오른쪽 가운데의 흰 네모 판, 원을 가로지르는 은색 막대 하나와 비스듬한 막대 둘, 왼쪽 위에서 지붕 위로 솟은 은색 날개.
# 추정·단순화: 원의 지름과 중심 높이, 상자·판·막대의 자리(사진에서 원 지름에 견준 비율로 옮김), 줄무늬의 간격. 유리 몸체는 detail.py 의 일반 타워가 세운다.
TOWER_STYLE['w85032872'] = dict(sty='curtain', g='#6f9299')
_ib, _ig = _bp('w85032872')
if _ib:
    d = np.array(_toward_road(_ig, '영동대로'), float); d /= np.hypot(*d); e = np.array([-d[1], d[0]]); c0 = np.array(_ig.centroid.coords[0]); H = _ib['h']; fh = _face_hit(_ig, d)   # e = 길에서 볼 때 오른쪽
    wide = max(abs(float((np.array(q) - c0) @ e)) for q in _ig.exterior.coords); R = min(wide * 1.0, H * .36); zc = H - R - 1.5; amb = MB()
    sv, rd, rd2, wh = mat_flat('#b9bec2'), mat_flat('#b8323a'), mat_flat('#7a2a32'), mat_flat('#eceeee')
    P3 = lambda u, v, o=1.0: (fh[0] + e[0] * u * R + d[0] * o, fh[1] + e[1] * u * R + d[1] * o, zc + v * R)
    def panel(u, v, w, h, m, o, mt=None, uv=None):   # 입면에 나란한 판(가운데 u, v / 크기 w, h — 원 반지름에 견준 비율), 유리에서 o m 띄움
        q = [P3(u - w / 2, v - h / 2, o), P3(u + w / 2, v - h / 2, o), P3(u + w / 2, v + h / 2, o), P3(u - w / 2, v + h / 2, o)]; amb.face(q, mt or m, uv)
        b0 = [P3(u - w / 2, v - h / 2, .15), P3(u + w / 2, v - h / 2, .15), P3(u + w / 2, v + h / 2, .15), P3(u - w / 2, v + h / 2, .15)]
        for k in range(4): amb.face([b0[k], b0[(k + 1) % 4], q[(k + 1) % 4], q[k]], m)
    for v in np.arange(-.78, .12, .07):   # 붉은 가는 가로줄: 원의 왼쪽 아래
        ul = -math.sqrt(max(0.0, .93 ** 2 - v * v)); ur = min(.18 - v * .55, math.sqrt(max(0.0, .9 ** 2 - v * v)))
        if ur - ul > .15: beam(amb, P3(ul, v, .6), P3(ur, v, .6), .32, rd, .32)
    beam(amb, P3(-.66, -.72, .9), P3(.62, -.72, .9), .5, rd, R * .075)                                   # 아래쪽 붉은 띠
    for u, v in ((-.28, .70), (.14, .84), (.27, .22), (-.12, .13), (-.52, .0), (.02, -.28), (-.50, -.40), (.34, -.12)): panel(u, v, .085, .15, rd, 2.2)   # 튀어나온 붉은 세로 상자
    pth, asp = sign_png('hdc', 'HDC', '#f1eeea', '#7a2a32', SERIF, pad=.3, mx=.35); panel(-.60, .60, .23, .23, rd2, 2.6, mat_tex(pth, 'sg_hdc'), [(0, 0), (1, 0), (1, 1), (0, 1)])
    panel(.52, -.20, .28, .30, wh, 1.6)                                                                  # 흰 네모 판
    beam(amb, P3(-.92, .16, 1.4), P3(.78, .34, 1.4), .7, sv, .9)                                          # 가로 막대
    for a_, b_ in (((-.74, -.76), (.06, .22)), ((-.44, -.86), (.32, .16))): beam(amb, P3(*a_, 1.9), P3(*b_, 1.9), .6, sv, .7)   # 비스듬한 막대 둘
    ring = [P3(math.cos(a), math.sin(a), 1.2) for a in np.linspace(0, 2 * math.pi, 49)]
    for q0, q1 in zip(ring[:-1], ring[1:]): beam(amb, q0, q1, 1.5, sv, 1.3)                               # 은회색 원 테
    m0, m1 = P3(-.97, .42, .4), P3(-.80, 0, .4); mt_ = (m1[0], m1[1], H + 15.0); mb_ = (m0[0], m0[1], H - 6.0)
    amb.face([mb_, (m1[0], m1[1], H - 6.0), mt_, (m0[0], m0[1], H + 9.0)], sv)                             # 지붕 위로 솟은 날개
    toonify(amb.build('ipark_art', 9792)); META[9792] = 'landmark:signs'
