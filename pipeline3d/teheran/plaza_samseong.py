# 삼성역 광장 빌더(무역센터 동남쪽 모퉁이). lm_build.py 끝에서 exec 로 읽는다(같은 전역: MB, mat_flat, skin, capf, obox, beam, taper, excavator, dumptruck, containers, _pits …).
# 자리·윤곽은 scene.json 의 'samseong'(prep_extra.py 가 위성 사진에서 따 온 값), 여기서는 형태·높이·색을 정한다.
# 네이버 지도 거리뷰(2026-07 촬영분: 영동대로 중앙 버스 정류장, 테헤란로 삼성역 사거리, 6번 출구 앞)와 위성 사진을 눈으로 보고 맞췄다. 사진은 저장소에 넣지 않았다. 글자·로고는 넣지 않는다.
#   - 밀레니엄 광장: 지면 높이의 원형 광장(동심 판석, 검은 돌 턱, 둘레의 내후성 강판 기둥, 세 단 받침 위 스테인리스 구), 서북쪽을 감싸는 초승달꼴 내리막 계단(흰 난간벽), 남쪽의 달걀꼴 흰 조형탑
#   - 코엑스 동측 광장: 회색 화강석 판석(5 m 마다 밝은 띠), 남쪽은 여러 색 돌 모자이크, 길가 잔디 띠와 엇갈린 잔디 네모, 아티움 앞 화단 띠와 붉은 꽃밭, 얕은 못 가운데 선 줄무늬 파빌리온, 붉은 꽃 화분, 가로등
#   - 5·6번 출구 앞 모퉁이: 복합환승센터 공사 야적장(가림벽·색 블록 벽화 담장, 파란 천막 창고, 현장 사무실 컨테이너, 초록 방진 덮개 흙더미, 크롤러 크레인, 펌프카)
#   - 호텔 앞: 소나무 화단, 깃대 줄, 유리 원형 지붕, 테헤란로 가의 플라스틱 방호벽
# 광장 안쪽은 공사 전(2017-08) 보행 거리뷰만 있어, 지금 위성 사진에 그대로 남아 있는 것(원형 광장·계단·파빌리온·조형탑)만 그 화면을 따랐다.
# 연출·추정: 초승달 계단 깊이(실제 약 5 m → 1.4 m), 조형탑 높이 17 m, 기둥 수와 자리, 야적장 안 장비·자재의 자리와 수, 담장 벽화의 무늬, 가로등 자리.
SS = S.get('samseong')
if SS and inwin(SS['court']['c'], 45.0, 200.0):
    NVp, Q0p = np.array(SS['nv']), np.array(SS['q0']); EVp = np.array([NVp[1], -NVp[0]]); CRT = SS['court']; CC = np.array(CRT['c'])
    def rdp(s, d): return Q0p + NVp * s - EVp * d                       # 영동대로 남행 차로 중심선 기준(prep_extra 의 rd)
    def EP(f, t, z): return (CC[0] + CRT['a'] * f * math.cos(t), CC[1] + CRT['b'] * f * math.sin(t), z)   # 원형 광장 타원 위의 점(f = 반지름 비)
    NE_ = 60; COURT = Polygon([EP(1.0, 2 * math.pi * k / NE_, 0)[:2] for k in range(NE_)])
    def esec(a0=0.0, a1=360.0): return [(math.radians(k * 360 / NE_), math.radians((k + 1) * 360 / NE_)) for k in range(NE_) if a0 <= k * 360 / NE_ < a1]
    def ering(mb, f0, f1, z, m, a0=0.0, a1=360.0):                      # 수평 타원 고리(안 f0 → 밖 f1)
        for t0, t1 in esec(a0, a1): mb.face([EP(f0, t0, z), EP(f1, t0, z), EP(f1, t1, z), EP(f0, t1, z)], m)
    def ewall(mb, f, z0, z1, m, a0=0.0, a1=360.0, tw=None, th=None):    # 안쪽을 보는 수직 타원 벽
        s = 0.0
        for t0, t1 in esec(a0, a1):
            a, b = EP(f, t0, 0), EP(f, t1, 0); L_ = math.hypot(b[0] - a[0], b[1] - a[1])
            uv = [((s + L_) / tw, z0 / th), (s / tw, z0 / th), (s / tw, z1 / th), ((s + L_) / tw, z1 / th)] if tw else None
            mb.face([(b[0], b[1], z0), (a[0], a[1], z0), (a[0], a[1], z1), (b[0], b[1], z1)], m, uv); s += L_
    def lines(g): return [g] if g.geom_type == 'LineString' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'LineString']
    def wallrun(mb, ln, z0, z1, m, th=.25, tw=None, tex_h=None, flip=False):   # 선을 따라 선 얇은 벽. tw 를 주면 길이 방향으로 되풀이하는 그림(왼쪽 면)
        cs = list(ln.coords); s = 0.0
        for a, b in zip(cs[:-1], cs[1:]):
            a, b = np.array(a[:2]), np.array(b[:2]); L_ = float(np.hypot(*(b - a)))
            if L_ < .05: continue
            d = (b - a) / L_; n_ = np.array([-d[1], d[0]]) * (th / 2)
            if tw:
                for sg in (1, -1) if not flip else (-1, 1):
                    p, q = (a + n_ * sg, b + n_ * sg) if sg == 1 else (b + n_ * sg, a + n_ * sg)
                    uv = [(s / tw, 0), ((s + L_) / tw, 0), ((s + L_) / tw, 1), (s / tw, 1)] if sg == 1 else [((s + L_) / tw, 0), (s / tw, 0), (s / tw, 1), ((s + L_) / tw, 1)]
                    mb.face([(*p, z0), (*q, z0), (*q, z1), (*p, z1)], m, uv)
                mb.face([(*(a + n_), z1), (*(b + n_), z1), (*(b - n_), z1), (*(a - n_), z1)], mat_flat('#f1efe9'))
            else: obox(mb, (a + b) / 2, d, L_ / 2, th / 2, z0, z1, m)
            s += L_
    def curb(mb, g, h=.26, w=.3, col='#dedbd2'):                         # 화단 돌 턱(안쪽은 지면 그림의 잔디가 그대로 보인다)
        for q in parts(g.difference(g.buffer(-w, join_style=2))):
            q = orient(q, 1.0); skin(mb, q, 0.0, lambda x, y: h, mat_flat(shade(col, .86)), 1, 1); capf(mb, q, lambda x, y: h, mat_flat(col))
    def tex_png(name, w, h, bg, draw):
        p = f'{TEXD}/ss_{name}.png'
        if not os.path.exists(p): im = Image.new('RGB', (w, h), bg); draw(ImageDraw.Draw(im), w, h); im.save(p)
        return p

    # ---- 바닥(지면 ID 1 → 분류 맵에서 보행 광장으로 읽힌다) ----
    # 북쪽(코엑스 동측 광장): 밝은 회색 화강석 판석, 5 m 마다 밝은 띠. 남쪽(밀레니엄 광장 둘레): 베이지·분홍·회색·검은 돌이 섞인 모자이크 판석
    PM = 10.0
    def _pave(d, w, h):
        rnd = random.Random(7); q = w // 8
        for i in range(8):
            for j in range(8): d.rectangle([i * q, j * q, (i + 1) * q - 1, (j + 1) * q - 1], fill=shade('#d3d2cc', 1 + rnd.uniform(-.04, .04)))
        for k in range(8): d.line([(k * q, 0), (k * q, h)], fill='#bdbcb6', width=1); d.line([(0, k * q), (w, k * q)], fill='#bdbcb6', width=1)
        bw = int(.34 * w / PM)
        for k in (0, 4):
            for c0 in ((k * q - bw, k * q + bw), (k * q - bw + w, k * q + bw + w)): d.rectangle([c0[0], 0, c0[1], h], fill='#ebeae4'); d.rectangle([0, c0[0], w, c0[1]], fill='#ebeae4')
    def _mosaic(d, w, h):
        rnd = random.Random(23); q = w // 8; cols = ['#dbd3c1'] * 5 + ['#cbcac0'] * 4 + ['#c78169'] * 2 + ['#b1968a'] + ['#8f9194'] * 2 + ['#e6e1d2'] * 2
        for i in range(8):
            for j in range(8): d.rectangle([i * q, j * q, (i + 1) * q - 1, (j + 1) * q - 1], fill=rnd.choice(cols))
        for _ in range(9): i, j = rnd.randrange(7), rnd.randrange(8); d.rectangle([i * q, j * q, (i + 2) * q - 1, (j + 1) * q - 1], fill=rnd.choice(cols))   # 두 칸짜리 긴 판
        d.rectangle([3 * q, 0, 3 * q + q // 2, h], fill='#7d7f82')   # 길 방향으로 이어지는 검은 돌 줄
    pmat = mat_tex(tex_png('pave', 240, 240, '#d3d2cc', _pave), 'ss_pave'); mmat = mat_tex(tex_png('mosaic', 240, 240, '#dbd3c1', _mosaic), 'ss_mosaic')
    green = unary_union([Polygon(r) for r in list(SS['lawn'].values()) + list(SS['bed'].values())])
    road = unary_union([ln.buffer(r['w'] / 2 + .7, cap_style=2) for ln, r in _DRV if ln.distance(Point(*CC)) < 230] + [Point(0, 0).buffer(.01)])
    ST = SS['stair']; SA0, SA1 = math.radians(ST['a0']), math.radians(ST['a1'])
    def SP(t, out, z): return (CC[0] + ST['a'] * math.cos(t), CC[1] + ST['b'] * math.sin(t), z) if out else EP(ST['f'], t, z)   # 초승달 계단의 바깥·안쪽 호
    NS = 28; STT = [SA0 + (SA1 - SA0) * k / NS for k in range(NS + 1)]
    STAIR = Polygon([SP(t, True, 0)[:2] for t in STT] + [SP(t, False, 0)[:2] for t in STT[::-1]])
    pools = unary_union([Polygon([np.array(w_['c']) + NVp * u * (w_['hl'] + 2.0) + EVp * v * (w_['hw'] + 2.0) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]) for w_ in SS['pavs']])
    slabp = P(SS['pave']).difference(unary_union([green, COURT, STAIR.buffer(.05), pools, road])).buffer(0); SOUTH = box(1000.0, 300.0, 1400.0, 547.5).intersection(Point(*CC).buffer(40.0))   # 모자이크 판석은 원형 광장 둘레만(그 밖은 회색 판석)
    mb = MB()
    for zone, m_ in ((slabp.difference(SOUTH), pmat), (slabp.intersection(SOUTH), mmat)):
        for g in parts(zone):
            if g.area < 1: continue
            for t in shapely.constrained_delaunay_triangles(g).geoms:
                q = list(orient(t, 1.0).exterior.coords)[:-1]
                mb.face([(x, y, .03) for x, y in q], m_, [(((x - Q0p[0]) * EVp[0] + (y - Q0p[1]) * EVp[1]) / PM, ((x - Q0p[0]) * NVp[0] + (y - Q0p[1]) * NVp[1]) / PM) for x, y in q])
    for k, r in SS['lawn'].items(): curb(mb, Polygon(r), .22 if k != 'strip' else .16)
    # 원형 광장 바닥: 동심 띠(밝은 판석 사이 검은 돌 고리)
    for f0, f1, col in ((.0, .30, '#c9c8c2'), (.30, .35, '#7d7f82'), (.35, .64, '#d5d3cb'), (.64, .69, '#7d7f82'), (.69, 1.0, '#c6c4bb')): ering(mb, f0, f1, .03, mat_flat(col))
    # 초승달 계단(지면 ID): 남쪽 끝에서 내려가 북서쪽(에스컬레이터 덮개 밑)이 가장 낮고, 북쪽 끝에서 다시 올라온다
    FZ = -1.4   # 바닥 높이: 굽기(step_maps)가 −1.55 m 보다 낮은 지면을 물로 읽으므로 그보다 얕게 둔다
    SZ = [FZ * min(1.0, (k + 1) / 3.0, (NS - k) / 8.0) for k in range(NS)]   # 조각마다의 디딤판 높이(북쪽 세 단, 남쪽 일곱 단)
    for k in range(NS):
        t0, t1, z = STT[k], STT[k + 1], SZ[k]; zp = SZ[k - 1] if k else 0.0
        mb.face([SP(t0, True, z), SP(t0, False, z), SP(t1, False, z), SP(t1, True, z)], mat_flat('#d9d6cd' if k % 2 else '#c6c3ba'))
        if abs(z - zp) > .01: mb.face([SP(t0, False, min(z, zp)), SP(t0, True, min(z, zp)), SP(t0, True, max(z, zp)), SP(t0, False, max(z, zp))], mat_flat('#a9a69d'))
    mb.face([SP(STT[NS], False, SZ[-1]), SP(STT[NS], True, SZ[-1]), SP(STT[NS], True, 0.0), SP(STT[NS], False, 0.0)], mat_flat('#a9a69d'))
    mb.build('ss_ground', 1)

    # ---- 밀레니엄 광장: 원형 광장의 돌 턱, 강철 기둥(내후성 강판, 높이 7–8 m), 계단꼴 받침 위 스테인리스 구, 초승달 계단의 흰 난간벽 ----
    mb = MB()
    for a0, a1 in ((340.0, 360.0), (0.0, 20.0), (70.0, 95.0), (235.0, 290.0)):   # 검은 화강석 턱(앉는 높이). 나머지 둘레는 열려 있다
        ewall(mb, 1.0, 0.0, .45, mat_flat('#5d6166'), a0, a1); ering(mb, 1.0, 1.05, .45, mat_flat('#6f7377'), a0, a1)
        for t0, t1 in esec(a0, a1): a, b = EP(1.05, t0, 0), EP(1.05, t1, 0); mb.face([(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], .45), (a[0], a[1], .45)], mat_flat('#5d6166'))
    for k, a_ in enumerate((18, 30, 41, 53, 66, 80, 196, 208, 221, 235, 250, 263, 277)):   # 강철 기둥: 북동쪽과 남서쪽에 두 무리로 줄지어 선다(거리뷰에서 센 수는 열두어 개)
        t = math.radians(a_); p = EP(.78 + .05 * (k % 2), t, 0); tg = np.array([-math.sin(t), math.cos(t)]); obox(mb, p[:2], tg, .32, .16, 0, 4.4 + (k * 7 % 5) * .45, mat_flat('#523d2d'), mat_flat('#67523e'))
    for r_, z_ in ((2.6, .0), (1.9, .18)): mb.cyl((CC[0], CC[1], z_ + .03), r_, .18, mat_flat('#55595e'), mat_flat('#6f7377'), n=24)   # 낮고 검은 두 단 받침
    blob(mb, (CC[0], CC[1], .4 + 1.15), 1.15, mat_flat('#dde3e3'), 1.0, 14)                                                                # 스테인리스 구
    for a0, a1 in ((120.0, 170.0), (296.0, 334.0)):   # 둘레 안쪽의 긴 곡선 벤치
        for t0, t1 in esec(a0, a1): a, b = EP(.93, t0, .03), EP(.93, t1, .03); beam(mb, (a[0], a[1], .42), (b[0], b[1], .42), .5, mat_flat('#756049'), .1); beam(mb, (a[0], a[1], .2), ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, .2), .12, mat_flat('#55595e'), .4)
    wm = mat_flat('#f1efe9')
    def ph(k): return 1.2 + 2.3 * max(0.0, (k - (NS - 6)) / 6.0)   # 난간벽 높이: 남쪽 끝으로 갈수록 솟는 흰 뱃머리꼴(거리뷰: 사람 키의 두 배쯤)
    for k in range(NS):   # 초승달 계단 둘레: 구덩이 안쪽 벽 + 흰 타일 난간벽
        t0, t1 = STT[k], STT[k + 1]; h0, h1 = ph(k), ph(k + 1)
        for out in (True, False):
            a, b = np.array(SP(t0, out, 0)[:2]), np.array(SP(t1, out, 0)[:2]); sg = .32 if out else -.32
            na, nb = (a - CC) / np.hypot(*(a - CC)) * sg, (b - CC) / np.hypot(*(b - CC)) * sg; oa, ob = a + na, b + nb
            q = [(*a, FZ), (*b, FZ), (*b, h1), (*a, h0)]; mb.face(q[::-1] if out else q, wm)            # 계단 쪽 면
            q = [(*oa, 0), (*ob, 0), (*ob, h1), (*oa, h0)]; mb.face(q if out else q[::-1], wm)           # 광장 쪽 면
            mb.face([(*a, h0), (*b, h1), (*ob, h1), (*oa, h0)], mat_flat('#fbfaf5'))
    a, b = SP(STT[NS], True, 0), SP(STT[NS], False, 0); mb.face([(a[0], a[1], 0), (b[0], b[1], 0), (b[0], b[1], ph(NS)), (a[0], a[1], ph(NS))], wm)   # 남쪽 끝 마구리
    o_ = toonify(mb.build('ss_court', 9760)); smooth_obj(o_, 40.0); META[9760] = 'landmark:millennium'
    _pits.append(STAIR); NOSKIRT = STAIR.buffer(3.0)   # 지면 판에서 계단 자리를 도려내고, 비탈 대신 위의 수직 벽을 쓴다

    # ---- 달걀꼴 조형탑(거리뷰: 은회색 판을 켜켜이 붙인 길쭉한 달걀꼴, 꼭대기에 비스듬히 걸친 금속 고리, 낮고 검은 둥근 받침) ----
    eg = SS['egg']; ex_, ey_ = eg['c']; EH, ER = eg['h'], eg['r']; mb = MB(); n = 18; prev = None
    def er(t): return ER * (.52 + .48 * math.sin(math.pi / 2 * t / .42)) if t < .42 else ER * max(0.0, 1 - ((t - .42) / .58) ** 2.0) ** .62   # 아래 2/5 가 가장 굵고 위로 뾰족하게 준다
    mb.cyl((ex_, ey_, 0), ER * 1.5, .35, mat_flat('#55595e'), mat_flat('#6f7377'), n=20)
    NR = 18
    for j in range(NR + 1):
        t = j / NR; r_ = max(.05, er(t)); ring = [(ex_ + r_ * math.cos(2 * math.pi * k / n), ey_ + r_ * math.sin(2 * math.pi * k / n), .35 + EH * t) for k in range(n)]
        if prev:
            m_ = mat_flat('#d5d1c3' if j % 2 else '#c6c4bb')
            for k in range(n): mb.face([prev[k], prev[(k + 1) % n], ring[(k + 1) % n], ring[k]], m_)
        prev = ring
    mb.face(prev, mat_flat('#d5d1c3'))
    ed = np.array([-.22, -.975]); ed /= np.hypot(*ed); eu = np.array([-ed[1], ed[0]]); hc = np.array([ex_, ey_, .35 + EH * .88])   # 고리: 꼭대기를 남쪽으로 기울여 두른 금속 띠
    hp = [tuple(hc + np.array([*(eu * 2.3 * math.cos(a)), 0]) + np.array([*(ed * .55), .84]) * 2.9 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)]
    for k in range(20): beam(mb, hp[k], hp[(k + 1) % 20], .42, mat_flat('#6f7377'))
    o_ = toonify(mb.build('ss_egg', 9761)); smooth_obj(o_, 60.0); META[9761] = 'landmark:plaza_art'

    # ---- 광장 시설: 파빌리온, 화분, 에스컬레이터 덮개, 꽃밭, 가로등, 벤치, 호텔 앞 화단·천막·유리 지붕 ----
    mb = MB()
    def _stripe(d, w, h):   # 4.4 m 한 벌: 청록 벽에 검은 띠 둘, 위쪽 흰 세로 날개 둘
        for x0_ in (.25, .75): d.rectangle([int(w * x0_), 0, int(w * (x0_ + .125)), h], fill='#22272b')
        for x0_ in (.09, .59): d.rectangle([int(w * x0_), 0, int(w * (x0_ + .07)), int(h * .62)], fill='#f1efe9')
        d.rectangle([0, h - 5, w, h], fill='#2f3438')
    sm = mat_tex(tex_png('stripe', 106, 82, '#7da8b8', _stripe), 'ss_stripe')
    for w_ in SS['pavs']:   # 얕은 못(검은 돌 턱 + 물) 가운데 선 줄무늬 파빌리온. 거리뷰: 청록 판에 검은 띠와 흰 세로 날개, 짙은 평지붕
        c = np.array(w_['c']); obox(mb, c, NVp, w_['hl'] + 2.0, w_['hw'] + 2.0, 0, .34, mat_flat('#5d6166'), mat_flat('#6f7377')); obox(mb, c, NVp, w_['hl'] + 1.65, w_['hw'] + 1.65, .34, .36, mat_flat('#7da8b8'), mat_flat('#7da8b8'))
        g = orient(Polygon([c + NVp * u * w_['hl'] + EVp * v * (w_['hw'] - .2) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]), 1.0); skin(mb, g, .3, lambda x, y: 3.5, sm, 4.4, 3.4)
        obox(mb, c, NVp, w_['hl'] + .3, w_['hw'] + .1, 3.5, 3.7, mat_flat('#3b4046'), mat_flat('#4a5057'))
        for u, v in ((-.6, 1), (.2, 1), (.7, -1), (-.2, -1)): q = c + NVp * u * (w_['hl'] + 1.0) + EVp * v * (w_['hw'] + 1.0); mb.cyl((q[0], q[1], .36), .07, .5, mat_flat('#fdfdf3'), n=4)   # 분수 물줄기
    for p in ((1180.5, 542.0), (1199.5, 541.0), (1207.0, 527.5), (1176.5, 499.5), (1196.0, 567.5), (1189.5, 589.0), (1181.0, 608.0)):   # 붉은 꽃을 심은 큰 화분(검은 대접꼴)
        taper(mb, p, np.array([1.0, 0.0]), .55, .55, 1.25, 1.25, 0, .65, mat_flat('#3b4046')); blob(mb, (p[0], p[1], .7), 1.15, mat_flat('#b6573c'), .45, 8); blob(mb, (p[0] + .3, p[1] - .2, .85), .6, mat_flat('#c78169'), .5, 6)
    cn = SS['canopy']; ca = np.array(cn['ax']) / np.hypot(*cn['ax']); cv = np.array([-ca[1], ca[0]]); c = np.array(cn['c'])   # 덮개: 유리 벽 + 둥근 유리 지붕
    for sv in (-1, 1): obox(mb, c + cv * sv * cn['hw'], ca, cn['hl'], .08, 0, 2.5, mat_flat('#7da8b8'))
    prof_ = [(cn['hw'] * math.cos(math.pi * j / 6), 2.5 + 1.0 * math.sin(math.pi * j / 6)) for j in range(7)]
    for (v0, z0), (v1, z1) in zip(prof_[:-1], prof_[1:]):
        a0_, a1_ = c - ca * (cn['hl'] + .3), c + ca * (cn['hl'] + .3); mb.face([(*(a0_ + cv * v1), z1), (*(a1_ + cv * v1), z1), (*(a1_ + cv * v0), z0), (*(a0_ + cv * v0), z0)], mat_flat('#6ea8dd' if (v0 + v1) > 0 else '#7cbefa'))
    rnd = random.Random(521)
    def _flower(d, w, h):
        for i in range(0, w, 3):
            for j in range(0, h, 3): d.rectangle([i, j, i + 2, j + 2], fill=rnd.choice(['#b6573c', '#c78169', '#b6573c', '#d9907a', '#c2603f', '#c78169', '#65ad4e', '#fbf3ee']))
    fm = mat_tex(tex_png('flower', 96, 96, '#b6573c', _flower), 'ss_flower')
    for k, r in SS['bed'].items():   # 꽃밭: 돌 턱 + 꽃 바닥(붉은·분홍 얼룩) + 꽃 덩어리
        g = Polygon(r); curb(mb, g, .34, .32); inn = g.buffer(-.32, join_style=2)
        for q in parts(inn):
            for t in shapely.constrained_delaunay_triangles(q).geoms:
                qq = list(orient(t, 1.0).exterior.coords)[:-1]; mb.face([(x, y, .3) for x, y in qq], fm, [(x / 8.0, y / 8.0) for x, y in qq])
            for p_ in _spots(q, max(2, int(q.area // 9)), rnd, .7): blob(mb, (p_[0], p_[1], .45), rnd.uniform(.45, .75), mat_flat(rnd.choice(['#c2603f', '#d08a72', '#b6573c', '#f3e3da', '#65ad4e'])), .6, 6)
    def lamp(p, h=7.0):
        mb.cyl((p[0], p[1], 0), .11, h, mat_flat('#59616a'), n=5); mb.box((p[0], p[1], h), .55, .2, .16, mat_flat('#e9ecee'), math.atan2(NVp[1], NVp[0]) + math.pi / 2)
    for s_ in np.arange(104.0, 212.0, 15.0): lamp(rdp(s_, SS['edge'] + 6.2))                               # 길가 가로등 줄
    for a_ in (35, 55, 305, 335): lamp(EP(1.32, math.radians(a_), 0)[:2], 6.0)                              # 원형 광장 동쪽 둘레
    for s_, d_ in ((112.0, 16.5), (126.0, 20.5), (140.0, 15.5), (156.0, 15.0), (170.0, 14.5)):             # 벤치(길 방향)
        p = rdp(s_, d_); obox(mb, p, NVp, 1.2, .26, 0, .45, mat_flat('#756049'), mat_flat('#998666'))
    for k, p in enumerate(SS['flags']):   # 호텔 진입로의 깃대 줄(거리뷰: 흰 깃대 여덟 개 남짓)
        mb.cyl((p[0], p[1], 0), .08, 9.0, mat_flat('#eceae4'), n=5); fd_ = np.array([.94, .34]) * 1.5
        mb.face([(p[0], p[1], 7.6), (p[0] + fd_[0], p[1] + fd_[1], 7.6), (p[0] + fd_[0], p[1] + fd_[1], 8.8), (p[0], p[1], 8.8)], mat_flat(('#fdfdf3', '#6ea8dd', '#fdfdf3', '#b6573c')[k % 4]))
    for k in range(4): p = SS['stone']; obox(mb, np.array(p) + np.array([.12, -.08]) * (k % 2), (math.cos(.3 * k), math.sin(.3 * k)), .62, .62, k * 1.2, k * 1.2 + 1.15, mat_flat('#caaf88' if k % 2 else '#dbc197'))   # 돌을 쌓아 올린 조형 기둥
    for k in range(24): p = np.array([1147.0, 445.6]) + np.array([.96, .28]) * k * 1.5; mb.box((p[0], p[1], 0), .7, .25, .85, mat_flat('#b6573c' if k % 2 else '#f3f1ea'), math.atan2(.28, .96))   # 테헤란로 가 플라스틱 방호벽(주황·흰색)
    dm = SS['dome']; dc = np.array(dm['c'])   # 호텔 차 대는 곳의 유리 원형 지붕
    for k in range(6): a_ = 2 * math.pi * k / 6; mb.cyl((dc[0] + (dm['r'] - .6) * math.cos(a_), dc[1] + (dm['r'] - .6) * math.sin(a_), 0), .16, 5.2, mat_flat('#c9cdd0'), n=6)
    mb.cyl((dc[0], dc[1], 5.2), dm['r'], .35, mat_flat('#c9cdd0'), mat_flat('#6ea8dd'), n=24); mb.cyl((dc[0], dc[1], 5.55), dm['r'] * .55, .3, mat_flat('#7da8b8'), mat_flat('#7cbefa'), n=24)
    toonify(mb.build('ss_kit', 9763)); META[9763] = 'landmark:plaza_kit'

    # ---- 길가 가림벽(광장과 영동대로 사이). 거리뷰: 버스 정류장 뒤는 흰 강판 + 옥색 방음망, 그 북쪽은 색 글자 벽화를 그린 흰 담장 ----
    mb = MB(); rnd = random.Random(1282)
    def _mural(dark):
        def f(d, w, h):
            r_ = random.Random(31 if dark else 17); cols = ['#5cac83', '#b6573c', '#efbe3e', '#394f63', '#6ea8dd'] + (['#f3f1ea'] * 2 if dark else [])
            x = 6
            while x < w - 20:
                bw = r_.randrange(16, 40); top = r_.randrange(10, 22)
                if r_.random() < .8:
                    c_ = r_.choice(cols); d.rounded_rectangle([x, top, x + bw, h - 16], radius=r_.choice([0, 6, 12]), fill=c_)
                    if r_.random() < .5: d.ellipse([x + bw // 4, top + 6, x + bw * 3 // 4, top + 6 + bw // 2], fill=r_.choice([c for c in cols if c != c_]))
                x += bw + r_.randrange(5, 16)
            for x in range(-h, w, 14): d.polygon([(x, h), (x + 7, h), (x + 14, h - 9), (x + 7, h - 9)], fill='#1c1c1c')   # 아래쪽 노랑·검정 빗금 띠
        return f
    MW_ = 24.0; mwh = mat_tex(tex_png('mural_w', 576, 62, '#f3f1ea', lambda d, w, h: (d.rectangle([0, h - 9, w, h], fill='#efbe3e'), _mural(False)(d, w, h))), 'ss_mural_w')
    mbk = mat_tex(tex_png('mural_k', 576, 62, '#1f2126', lambda d, w, h: (d.rectangle([0, h - 9, w, h], fill='#efbe3e'), _mural(True)(d, w, h))), 'ss_mural_k')
    fl = LineString([rdp(93.0, SS['edge'] - .15), rdp(152.0, SS['edge'] - .15)]); fl2 = LineString([rdp(152.0, SS['edge'] - .15), rdp(214.0, SS['edge'] - .15)])
    wallrun(mb, fl, 0, 2.4, mat_flat('#eceae4'), .22); wallrun(mb, fl, 2.4, 3.5, mat_flat('#8fd9b6'), .08); wallrun(mb, fl2, 0, 2.6, mwh, .25, MW_, 2.6)
    for s_ in np.arange(0, fl.length, 6.0): p = fl.interpolate(float(s_)); mb.cyl((p.x, p.y, 0), .09, 3.6, mat_flat('#9aa1a6'), n=4)
    mb.build('ss_fence', 9765); META[9765] = 'landmark:site_fence'

    # ---- 공사 야적장 ----
    yard = Polygon(SS['yard']); mb = MB()
    gl = LineString([(1199.9, 461.2), (1221.9, 469.5)]); gate = gl.buffer(1.3, cap_style=2); ring = yard.buffer(-.35).exterior.difference(gate)   # 테헤란로 쪽 출입문 자리
    maj = unary_union([ln for ln, r in _DRV if r['cls'] == 'major' and r['hw'] != 'primary_link' and ln.distance(yard) < 30]); th_ = unary_union([ln for ln, r in _DRV if r['name'] == '테헤란로' and ln.distance(yard) < 30])
    for ln in lines(ring):
        cs = list(ln.coords)
        for a, b in zip(cs[:-1], cs[1:]):
            seg = LineString([a, b]); mid = seg.interpolate(.5, normalized=True)
            if seg.length < .1: continue
            if mid.distance(maj) < 12.5 and mid.distance(th_) < 12.5 and mid.x < 1200: wallrun(mb, seg, 0, 2.0, mat_flat('#c6c4bb'), .3)   # 테헤란로 서쪽 구간: 낮은 회색 가벽
            elif mid.distance(maj) < 12.5:   # 길 쪽: 벽화 담장(테헤란로 쪽은 검은 바탕)
                wallrun(mb, seg, 0, 2.6, mbk if mid.distance(th_) < 12.5 else mwh, .25, MW_, 2.6)
            else: wallrun(mb, seg, 0, 2.4, mat_flat('#eceae4'), .22); wallrun(mb, seg, 2.4, 3.5, mat_flat('#8fd9b6'), .08)
    gd = np.array(gl.coords[1]) - np.array(gl.coords[0]); gL = float(np.hypot(*gd)); gd /= gL   # 접이식 출입문(스테인리스 마름모 살): 기둥 + 엇갈린 살
    for k in range(int(gL // 1.1) + 1):
        p0 = np.array(gl.coords[0]) + gd * k * 1.1; mb.cyl((p0[0], p0[1], 0), .05, 1.75, mat_flat('#c1beb5'), n=4)
        if k < int(gL // 1.1): p1 = p0 + gd * 1.1; beam(mb, (*p0, .25), (*p1, 1.6), .06, mat_flat('#cbcac0')); beam(mb, (*p0, 1.6), (*p1, .25), .06, mat_flat('#cbcac0'))
    FD = np.array(SS['fence'][2]) - np.array(SS['fence'][1]); FD /= np.hypot(*FD); FN = np.array([FD[1], -FD[0]])   # 서쪽 가림벽 방향(북북동)과 그 오른쪽(야적장 안쪽)
    def shed(c, ax, hl, hw, h, roof, wall='#dfe3e6'):   # 천막·판넬 창고: 낮은 벽 + 박공 지붕
        ax = np.array(ax) / np.hypot(*ax); nv = np.array([-ax[1], ax[0]]); c = np.array(c); obox(mb, c, ax, hl, hw, 0, h, mat_flat(wall))
        for sv in (-1, 1):
            a0_, a1_ = c - ax * (hl + .2), c + ax * (hl + .2)
            mb.face([(*(a0_ + nv * sv * (hw + .25)), h - .1), (*(a1_ + nv * sv * (hw + .25)), h - .1), (*a1_, h + hw * .42), (*a0_, h + hw * .42)][::sv], mat_flat(roof if sv > 0 else shade(roof, .86)))
        for a_ in (c - ax * hl, c + ax * hl): mb.face([(*(a_ - nv * hw), h), (*(a_ + nv * hw), h), (*a_, h + hw * .42)], mat_flat(wall))
    f1 = np.array(SS['fence'][1])
    shed(f1 + FD * 20.0 + FN * 3.6, FD, 15.5, 2.3, 2.9, '#6183a3')                    # 가림벽 안쪽의 긴 파란 천막 창고
    shed(f1 + FD * 3.2 + FN * 5.0, FD, 3.6, 2.6, 3.2, '#7fd3ae', '#eef1f0')           # 옥색 지붕 창고
    oc = f1 + FD * 22.0 + FN * 14.0                                                   # 현장 사무실: 컨테이너 2층 두 줄
    for o in (-2.7, 2.7):
        for l_ in range(2): obox(mb, oc + FN * o, FD, 9.0, 2.45, l_ * 2.7, l_ * 2.7 + 2.7, mat_flat('#e7e8e4' if l_ else '#d5d8d6'), mat_flat('#b9bec2'))
        for k in range(-3, 4): obox(mb, oc + FN * (o + (2.47 if o > 0 else -2.47)) + FD * k * 2.5, FD, .7, .03, 3.6, 4.6, mat_flat('#3f5567'))
        for k in range(-3, 4): obox(mb, oc + FN * o + FD * k * 2.6, FD, .06, 2.45, 5.4, 5.48, mat_flat('#8e959b'))   # 컨테이너 지붕 이음
    obox(mb, oc + FD * 9.6, FD, .6, 4.4, 0, 5.4, mat_flat('#a8adb1')); obox(mb, oc - FN * 6.6 + FD * 2, FD, 3.0, 1.25, 0, 2.6, mat_flat('#567890'), mat_flat('#47627c'))
    def stack(p, ang, n, col, sx=1.1, sy=.9, hz=.55):   # 자재 더미(판재·관·철근 묶음)
        d = np.array([math.cos(ang), math.sin(ang)]); nv = np.array([-d[1], d[0]])
        for i in range(n):
            for j in range(rnd.randrange(1, 4)): obox(mb, np.array(p) + nv * i * (sy * 2 + .35), d, sx, sy, j * hz, j * hz + hz - .05, mat_flat(shade(col, 1 + rnd.uniform(-.08, .08))))
    ta = math.atan2(.352, .936)   # 테헤란로 방향
    stack((1241.0, 487.5), ta, 5, '#a9adb0'); stack((1244.5, 492.5), ta, 4, '#b9bcbd'); stack((1221.5, 482.5), ta, 4, '#a9adb0', 1.3)
    stack((1168.0, 458.5), ta, 5, RUST, 2.6, .5, .4); stack((1178.0, 463.5), ta, 4, '#8d8f8c', 2.2, .6, .5); stack((1227.5, 476.0), ta, 3, '#f1efe9', 1.5, .9, .5)   # 철근, 강관, 흰 가림판 더미
    for p_, n_ in (((1158.0, 462.0), 2), ((1229.0, 498.0), 3), ((1247.0, 501.5), 2)): containers(mb, p_, ta + (math.pi / 2 if n_ == 2 else 0), n_, rnd, 1)
    for p_, s_ in (((1184.0, 476.5), 3.4), ((1193.0, 470.0), 2.8), ((1236.5, 482.0), 2.4)): obox(mb, p_, (math.cos(ta), math.sin(ta)), s_, 1.6, 0, 1.3, mat_flat('#47627c'), mat_flat('#6183a3'))   # 파란 방수포 덮은 자재
    mc = np.array([1209.0, 477.0]); prev = None   # 초록 방진 덮개를 씌운 흙더미(거리뷰: 출입문 바로 뒤)
    for j, (rf, zf) in enumerate(((1.0, 0.0), (.78, .5), (.5, .86), (.2, 1.0))):
        ring_ = [(mc[0] + 7.6 * rf * math.cos(2 * math.pi * k / 11 + .3) * (1 + .12 * math.sin(k * 2.1)), mc[1] + 4.6 * rf * math.sin(2 * math.pi * k / 11 + .3) * (1 + .1 * math.cos(k * 1.7)), 3.1 * zf) for k in range(11)]
        if prev:
            for k in range(11): mb.face([prev[k], prev[(k + 1) % 11], ring_[(k + 1) % 11], ring_[k]], mat_flat('#569b4b' if (j + k) % 3 else '#65ad4e'))
        prev = ring_
    mb.face(prev, mat_flat('#65ad4e'))
    excavator(mb, (1220.5, 481.5), 0.0, 2.9, '#efbe3e'); excavator(mb, (1231.0, 493.0), 0.0, .5, '#efbe3e'); dumptruck(mb, (1189.0, 462.5), 0.0, ta, rnd); dumptruck(mb, (1238.0, 505.0), 0.0, math.atan2(NVp[1], NVp[0]), rnd)
    def crawler(p, ang, L=36.0, el=72.0, col='#4f9070'):   # 크롤러 크레인: 무한궤도 + 운전실 + 격자 붐(굵기는 그림에서 보이게 과장)
        d = np.array([math.cos(ang), math.sin(ang)]); nv = np.array([-d[1], d[0]]); p = np.array(p); m, dk = mat_flat(col), mat_flat(shade(col, .7))
        for sv in (-1, 1): obox(mb, p + nv * sv * 2.1, d, 3.6, .65, 0, 1.1, mat_flat('#33363a'))
        obox(mb, p, d, 3.0, 1.9, 1.1, 3.3, m, dk); obox(mb, p - d * 3.6, d, .9, 1.9, 1.3, 3.0, mat_flat('#6f7478')); obox(mb, p + d * 1.9 + nv * 1.2, d, 1.0, .7, 3.3, 4.6, mat_flat('#e9ece8'))
        e = math.radians(el); bd = np.array([d[0] * math.cos(e), d[1] * math.cos(e), math.sin(e)]); b0 = np.array([*(p + d * 2.2), 2.6]); tip = b0 + bd * L
        up = np.cross(np.array([*nv, 0.0]), bd); P4 = lambda t, u, v, w: tuple(b0 + bd * t + np.array([*nv, 0.0]) * u * w + up * v * w)
        for t in np.arange(0, L, 3.0):
            t1 = min(L, t + 3.0); w0, w1 = .75 * (1 - .45 * t / L), .75 * (1 - .45 * t1 / L)
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)): beam(mb, P4(t, u, v, w0), P4(t1, u, v, w1), .2, m)
            beam(mb, P4(t, -1, -1, w0), P4(t1, 1, -1, w1), .12, m); beam(mb, P4(t, -1, 1, w0), P4(t1, 1, 1, w1), .12, m); beam(mb, P4(t, -1, -1, w0), P4(t1, -1, 1, w1), .12, m); beam(mb, P4(t, 1, -1, w0), P4(t1, 1, 1, w1), .12, m)
        mast = np.array([*(p - d * 1.0), 3.3]); mt = mast + np.array([*(-d * 3.0), 9.0]); beam(mb, tuple(mast), tuple(mt), .3, dk); beam(mb, tuple(mt), tuple(tip), .09, mat_flat('#3a3a3c')); beam(mb, tuple(mt), (*(p - d * 3.8), 3.0), .09, mat_flat('#3a3a3c'))
        hk = tip - np.array([0, 0, 1.0]) * (tip[2] - 9.0); beam(mb, tuple(tip), tuple(hk), .08, mat_flat('#3a3a3c')); mb.box((hk[0], hk[1], hk[2] - 1.0), .35, .3, 1.0, mat_flat('#efbe3e'))
    crawler((1239.0, 512.5), math.atan2(NVp[1], NVp[0]) + .5, 40.0, 82.0)   # 거리뷰: 모퉁이에 거의 곧게 선 청록 격자 붐
    def pumpcar(p, ang, col='#b6573c'):   # 콘크리트 펌프카: 트럭 + 접이식 붐(세 마디)
        d = np.array([math.cos(ang), math.sin(ang)]); p = np.array(p); m = mat_flat(col)
        obox(mb, p, d, 4.6, 1.25, 0, 1.2, mat_flat('#2c2d30')); obox(mb, p + d * 3.4, d, 1.1, 1.2, 1.2, 3.0, mat_flat('#e9e9e4'), mat_flat('#c9c9c4')); obox(mb, p - d * .8, d, 2.6, 1.15, 1.2, 2.2, m)
        k0 = np.array([*(p - d * .5), 2.2]); k1 = k0 + np.array([*(d * 1.5), 15.0]); k2 = k1 + np.array([*(d * 10.5), 5.5]); k3 = k2 + np.array([*(d * 6.0), -9.0])
        for a_, b_, w_ in ((k0, k1, .55), (k1, k2, .45), (k2, k3, .35)): beam(mb, tuple(a_), tuple(b_), w_, m)
        beam(mb, tuple(k3), (k3[0], k3[1], k3[2] - 5.0), .16, mat_flat('#3a3a3c'))
    pumpcar((1246.0, 520.0), math.atan2(NVp[1], NVp[0]) + math.pi)
    if mb.f: mb.build('ss_yard', 9762); META[9762] = 'landmark:site_yard'
    print('samseong plaza built', flush=True)
