# 테헤란로 일반 건물의 세부. lm_build.py 끝에서 exec 로 읽는다(같은 전역: MB, mat_flat, mat_tex, skin, capf, obox, beam, ring_runs, grid_tex, finwall_tex, roof_std, sign_png, wall_strip …).
# gen_area.py 의 일반 빌더 셋을 이 지역 것으로 바꾼다: modern(저층: 빌라·주택·상가·근린 사무실), apartment(아파트 동), tower(45 m 이상 일반 타워).
# 생김새는 네이버 지도 거리뷰를 눈으로 보고 정했다(2026-11-13: 대치·역삼·논현·삼성동 주택가 골목 5곳, 아파트 단지 8곳, 테헤란로 150 m 간격 23곳). 사진은 저장소에 넣지 않았다.
# 건물마다 실제 외장을 맞춘 것이 아니라, 거리뷰에서 본 유형을 건물 종류·크기·면한 길에 따라 고정 난수로 나눠 준 것이다(같은 건물은 다시 렌더해도 같다).

def _png(name, w, h, bg, draw):
    p = f'{TEXD}/{name}.png'
    if not os.path.exists(p): im = Image.new('RGB', (w, h), bg); draw(ImageDraw.Draw(im)); im.save(p)
    return p
def _pick(r, pairs): return r.choices([k for k, _ in pairs], [w for _, w in pairs])[0]

# ================= 저층: 빌라·주택·상가·근린 사무실 =================
# 거리뷰에서 본 것: 3–5층 다세대(화강석 판·붉은 벽돌·흰 타일·짙은 고벽돌), 1층은 기둥만 선 필로티 주차장이거나 간판 띠를 단 가게, 옥상은 초록·회색 방수 바닥에 옥탑(계단실)·실외기·물탱크,
# 큰길 뒤 근린 사무실은 석재 격자·짙은 금속 패널·작은 유리 커튼월. 단독주택은 드물고 경사 지붕(주황·청회색 기와)이다.
VST = {  # 벽, 줄눈·그늘, 창틀, 유리, 무늬
    'granite': ('#cfcbc2', '#b3aea4', '#5c6066', '#34444f', 'panel'), 'granite_w': ('#e3e0d8', '#c7c3ba', '#6a6e74', '#3a4a57', 'panel'), 'granite_d': ('#8f8c86', '#77746e', '#3c3f44', '#2c3a45', 'panel'),
    'tile_w': ('#eeece6', '#d6d3cb', '#8b8f94', '#3d4d5a', 'tile'), 'brick_r': ('#a9523c', '#8a3f2e', '#ece4d4', '#2f3c48', 'brick'), 'brick_b': ('#8a5b45', '#6f4636', '#e2d8c6', '#2f3c48', 'brick'),
    'brick_y': ('#c8a67f', '#ac8a64', '#f2eadb', '#34444f', 'brick'), 'brick_k': ('#5d5551', '#48413e', '#d9d4cb', '#2a343d', 'brick'), 'stucco_w': ('#ebe6da', '#d5cfc0', '#7d8086', '#34444f', 'plain'),
    'stucco_y': ('#e3d2ac', '#ccb98f', '#f4eddc', '#34444f', 'plain'), 'concrete': ('#aeb0ae', '#989a98', '#44484d', '#2f3d49', 'plain'), 'metal_k': ('#4a4d52', '#3a3d42', '#24272b', '#5d7386', 'metal'),
    'curtain': ('#6f98ad', '#56788c', '#d9e0e4', '#5d87a0', 'curtain'),
}
SIGNC = ['#c8473c', '#2f6fb3', '#e0a52e', '#3d8f5a', '#f2f0ea', '#2b2e33', '#e8762c', '#7a4fa0']
CARC = ['#f4f4f0', '#c9ccd0', '#2a2c30', '#7d838a', '#33507a', '#a8322c']
def villa_atlas(st):
    """입면 그림 5칸 × 3줄(칸 = 3.2 × 3.2 m). 0줄 위층(창 넷 + 빈 벽), 1줄 1층 가게(간판 띠·진열창·문), 2줄 1층 필로티(기둥 사이 주차)."""
    wall, dark, frame, glass, pat = VST[st]; C = 102
    def draw(d):
        rnd = random.Random(zlib.crc32(st.encode())); g2 = shade(glass, 1.45)
        for row in range(3):
            for col in range(5):
                ox, oy = col * C, row * C
                if pat == 'panel':
                    for y in range(0, C, 26): d.line([(ox, oy + y), (ox + C, oy + y)], fill=dark)
                    for x in range(0, C, 51): d.line([(ox + x, oy), (ox + x, oy + C)], fill=dark)
                elif pat == 'brick':
                    for y in range(0, C, 4):
                        d.line([(ox, oy + y), (ox + C - 1, oy + y)], fill=dark)
                        for x in range((y // 4 % 2) * 6, C, 12): d.line([(ox + x, oy + y), (ox + x, oy + y + 3)], fill=dark)
                elif pat == 'tile':
                    for y in range(0, C, 8): d.line([(ox, oy + y), (ox + C, oy + y)], fill=dark)
                    for x in range(0, C, 8): d.line([(ox + x, oy), (ox + x, oy + C)], fill=dark)
                elif pat == 'metal':
                    for y in range(0, C, 13): d.line([(ox, oy + y), (ox + C, oy + y)], fill=dark)
                else: d.line([(ox, oy + C - 2), (ox + C, oy + C - 2)], fill=dark)
                if col == 4: continue
                def win(x0, y0, x1, y1, bars=1):
                    d.rectangle([ox + x0 - 2, oy + y0 - 2, ox + x1 + 2, oy + y1 + 2], fill=frame); d.rectangle([ox + x0, oy + y0, ox + x1, oy + y1], fill=glass)
                    d.polygon([(ox + x0, oy + y1), (ox + x0, oy + (y0 + y1) // 2), (ox + (x0 + x1) // 2, oy + y0), (ox + x0 + (x1 - x0) * 3 // 4, oy + y0)], fill=g2)
                    for k in range(1, bars + 1): xx = x0 + (x1 - x0) * k // (bars + 1); d.line([(ox + xx, oy + y0), (ox + xx, oy + y1)], fill=frame, width=2)
                if row == 0:
                    if pat == 'curtain':   # 유리 커튼월: 칸 전체가 유리, 층 사이 띠
                        d.rectangle([ox, oy, ox + C, oy + C], fill=glass); d.rectangle([ox, oy + C - 22, ox + C, oy + C], fill=wall)
                        for x in (0, 34, 68): d.rectangle([ox + x, oy, ox + x + 2, oy + C], fill=frame)
                        if col == 1: d.polygon([(ox, oy + C - 22), (ox, oy + 40), (ox + 50, oy)], fill=g2)
                    elif col == 0: win(24, 26, 78, 68); d.rectangle([ox + 20, oy + 71, ox + 82, oy + 74], fill=dark)
                    elif col == 1:   # 발코니 창 + 난간
                        win(12, 22, 90, 76, 2)
                        for y in (60, 68, 76): d.line([(ox + 10, oy + y), (ox + 92, oy + y)], fill='#d9d9d2', width=2)
                    elif col == 2: win(26, 24, 76, 62); d.rectangle([ox + 30, oy + 70, ox + 56, oy + 86], fill='#e4e4de', outline='#8e8e88'); d.ellipse([ox + 37, oy + 72, ox + 49, oy + 84], outline='#8e8e88')
                    else: win(14, 30, 44, 60, 0); win(60, 30, 90, 60, 0)
                elif row == 1:   # 가게: 간판 띠(글자 대신 흰 조각) + 진열창 + 문
                    sc = SIGNC[rnd.randrange(len(SIGNC))]; fg = '#2b2e33' if sc in ('#f2f0ea', '#e0a52e') else '#f6f5f0'
                    d.rectangle([ox + 2, oy + 4, ox + C - 3, oy + 26], fill=sc); x = 10
                    while x < C - 22: w_ = rnd.randrange(6, 15); d.rectangle([ox + x, oy + 10, ox + x + w_, oy + 20], fill=fg); x += w_ + rnd.randrange(3, 7)
                    d.rectangle([ox + 4, oy + 30, ox + C - 5, oy + C - 4], fill=frame); d.rectangle([ox + 7, oy + 33, ox + C - 40, oy + C - 10], fill=glass)
                    d.polygon([(ox + 7, oy + C - 10), (ox + 7, oy + 52), (ox + 38, oy + 33)], fill=g2); d.rectangle([ox + C - 36, oy + 33, ox + C - 8, oy + C - 4], fill='#3d342c'); d.rectangle([ox + C - 32, oy + 38, ox + C - 12, oy + 64], fill=g2)
                else:            # 필로티: 보 아래가 뚫려 있고 기둥만 선다. 안쪽은 어둡고 차가 서 있다
                    d.rectangle([ox, oy + 18, ox + C, oy + C], fill='#2f3237'); d.rectangle([ox, oy + C - 5, ox + C, oy + C], fill='#55585d')
                    for x in (0, C - 12): d.rectangle([ox + x, oy + 18, ox + x + 11, oy + C], fill=wall); d.line([(ox + x, oy + 18), (ox + x, oy + C)], fill=dark)
                    if col in (0, 2):
                        cc = CARC[rnd.randrange(len(CARC))]; d.rounded_rectangle([ox + 20, oy + 62, ox + 84, oy + C - 6], 6, fill=cc); d.rectangle([ox + 28, oy + 54, ox + 76, oy + 66], fill='#3c4a57')
                        for x in (30, 72): d.ellipse([ox + x - 6, oy + C - 14, ox + x + 6, oy + C - 2], fill='#1c1d20')
                    elif col == 3: d.rectangle([ox + 34, oy + 40, ox + 70, oy + C - 5], fill=frame); d.rectangle([ox + 38, oy + 44, ox + 66, oy + C - 5], fill=g2); d.rectangle([ox + 16, oy + 60, ox + 28, oy + 76], fill='#b9bcc0')
    return _png('villa_' + st, C * 5, C * 3, wall, draw)
def vwalls(mb, poly, z0, z1, st, ground, seed, flh, bay=3.2):
    """gen_area.walls 와 같은 칸 나눔. 다른 점: 창 종류를 칸(세로 줄)마다 정해 층마다 같은 자리에 같은 창이 오고, ground = 0 일반 벽 / 1 가게 / 2 필로티."""
    tex = mat_tex(villa_atlas(st), 'va_' + st); rnd = random.Random(seed); nfl = max(1, round((z1 - z0) / flh)); fh = (z1 - z0) / nfl
    for ring in [poly.exterior] + list(poly.interiors):
        for seq in ring_runs(list(ring.coords)):
            s = _arc(seq); L = s[-1]
            if L < 0.05: continue
            nb = max(1, round(L / bay)) if L >= 2.2 else 1
            for k in range(nb):
                pts = _sub(seq, s, L * k / nb, L * (k + 1) / nb); sa, sb = pts[0][1], pts[-1][1]; cu = 4 if L < 2.2 or rnd.random() < .08 else rnd.choice([0, 0, 1, 1, 2, 3]); cg = rnd.choice([0, 1, 2, 3])
                for f in range(nfl):
                    row = ground if (f == 0 and ground) else 0; col = 4 if L < 2.2 else (cg if row else cu)
                    u0, u1 = col / 5, (col + 1) / 5; v1 = 1 - row / 3; v0 = v1 - 1 / 3; za, zb = z0 + f * fh, z0 + (f + 1) * fh
                    for (p, sp), (q, sq) in zip(pts[:-1], pts[1:]):
                        if math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-4: continue
                        ua, ub = u0 + (u1 - u0) * (sp - sa) / max(sb - sa, 1e-9), u0 + (u1 - u0) * (sq - sa) / max(sb - sa, 1e-9)
                        mb.face([(p[0], p[1], za), (q[0], q[1], za), (q[0], q[1], zb), (p[0], p[1], zb)], tex, [(ua, v0), (ub, v0), (ub, v1), (ua, v1)])
                    if row == 1 and rnd.random() < .5 and len(pts) == 2:   # 차양(곧은 칸만)
                        p, q = pts[0][0], pts[-1][0]; Lc = math.hypot(q[0] - p[0], q[1] - p[1]) or 1; nx, ny = (q[1] - p[1]) / Lc, -(q[0] - p[0]) / Lc; am = mat_flat(rnd.choice(AWN[:5]))
                        mb.face([(p[0], p[1], za + 2.75), (q[0], q[1], za + 2.75), (q[0] + nx * .8, q[1] + ny * .8, za + 2.3), (p[0] + nx * .8, p[1] + ny * .8, za + 2.3)], am)
def hiproof(mb, poly, z, col, over=.45, step=.55, rise=.36):
    """경사 지붕(우진각 근사): 처마선에서 안쪽으로 층층이 올린다. 임의 평면에 맞는다."""
    for k in range(16):
        qs = [q for q in parts(poly.buffer(over - k * step, join_style=2)) if q.area > .5]
        if not qs: break
        for q in qs: q = orient(q, 1.0); skin(mb, q, z, lambda x, y: z + rise, mat_flat(shade(col, .84)), 1, 1); capf(mb, q, lambda x, y: z + rise, mat_flat(shade(col, 1 + .06 * (k % 2))))
        z += rise
DECKC = ['#5aa583', '#63ad8c', '#58a17d', '#5aa583', '#a5a39c', '#a5a39c', '#8f9296', '#4a4d55', '#b0604a']
TILEC = ['#c2603f', '#b4664a', '#8a5a44', '#5a6c7d', '#4d5258', '#4f7f6a']
VILLA = [('granite', 20), ('granite_w', 12), ('brick_r', 15), ('brick_b', 9), ('brick_y', 6), ('brick_k', 8), ('tile_w', 12), ('stucco_w', 8), ('stucco_y', 4), ('concrete', 6)]
SHOPB = [('granite', 14), ('granite_w', 12), ('granite_d', 10), ('metal_k', 12), ('curtain', 18), ('tile_w', 12), ('concrete', 8), ('brick_k', 8), ('brick_r', 6)]
_modern_base = modern
def modern(bd, idx):
    b0 = S['buildings'][idx - 10000]; k = b0['kind']
    if k in ('roof', 'carport', 'shed', 'garage', 'kiosk', 'hut', 'toilets', 'parking', 'greenhouse'): return _modern_base(bd, idx)   # 작은 부속 건물은 공용 규칙 그대로
    poly = orient(Polygon(bd['rings'][0], bd['rings'][1:]).buffer(0), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 4: return
    h = max(3.0, bd['h']); r = random.Random(b0['seed'] * 13 + 5); ar = poly.area; nfl = max(1, round(h / 3.3)); rd = b0.get('rd', ''); mb = MB()
    civic = k in ('school', 'university', 'college', 'kindergarten', 'hospital', 'public', 'government', 'church', 'civic', 'temple')
    house = k in ('house', 'detached') or (ar < 120 and nfl <= 2 and r.random() < .55)
    if civic: st, ground = r.choice(['granite_w', 'tile_w', 'brick_r', 'stucco_w', 'brick_y']), 0
    elif house: st, ground = r.choice(['brick_r', 'stucco_w', 'stucco_y', 'brick_b', 'granite_w', 'tile_w']), 0
    elif k in ('commercial', 'retail', 'office', 'bank', 'hotel') or rd == 'major' or h > 20 or ar > 700: st, ground = _pick(r, SHOPB), (1 if (rd or r.random() < .5) else 0)
    else: st, ground = _pick(r, VILLA), (1 if (rd == 'minor' and r.random() < .28) else 2 if (nfl >= 3 and r.random() < .62) else 0)
    wall, dark = VST[st][0], VST[st][1]; wallm = mat_flat(wall); ang = math.atan2(*(np.subtract(poly.exterior.coords[1], poly.exterior.coords[0])[::-1]))
    vwalls(mb, poly, 0, h, st, ground, b0['seed'], h / nfl)
    if house:   # 경사 지붕 + 처마 밑
        mb.face([(x, y, h) for x, y in list(orient(poly.buffer(.45, join_style=2), -1.0).exterior.coords)[:-1]], mat_flat(shade(wall, .7))); hiproof(mb, poly, h, r.choice(TILEC))
        return mb.build('b%d' % idx, idx)
    deck = mat_flat(r.choice(DECKC)); inner = poly.buffer(-0.28, join_style=2)
    if inner.geom_type == 'Polygon' and inner.area > 6 and not inner.interiors and not poly.interiors:   # 파라펫
        zt = h + 0.55
        for ring, flip in ((poly.exterior, False), (inner.exterior, True)):
            c = list(ring.coords)
            for a, q in zip(c[:-1], c[1:]): pts = [(a[0], a[1], h), (q[0], q[1], h), (q[0], q[1], zt), (a[0], a[1], zt)]; mb.face(pts[::-1] if flip else pts, wallm)
        for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms: mb.face([(x, y, zt) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat(dark))
        mb.face([(x, y, h) for x, y in list(orient(inner, 1.0).exterior.coords)[:-1]], deck)
    else:
        for t in shapely.constrained_delaunay_triangles(poly).geoms: mb.face([(x, y, h) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], deck)
        inner = poly
    def spot(area):
        if area.is_empty: return None
        x0, y0, x1, y1 = area.bounds
        for _ in range(30):
            p = Point(r.uniform(x0, x1), r.uniform(y0, y1))
            if area.contains(p): return p.x, p.y
    a1, a2 = inner.buffer(-1.2), inner.buffer(-2.4)
    if nfl >= 3 and r.random() < .62 and (s := spot(a2)):   # 옥탑(계단실): 벽 색 상자 + 조금 내민 지붕 판 + 문
        mb.box((s[0], s[1], h), 1.7, 2.0, 2.5, wallm, ang); mb.box((s[0], s[1], h + 2.5), 1.95, 2.25, .18, mat_flat(shade(wall, .78)), ang)
        dx, dy = math.cos(ang), math.sin(ang); px, py = s[0] + dx * 1.72, s[1] + dy * 1.72; mb.face([(px + dy * .5, py - dx * .5, h + .05), (px - dy * .5, py + dx * .5, h + .05), (px - dy * .5, py + dx * .5, h + 2.0), (px + dy * .5, py - dx * .5, h + 2.0)], mat_flat('#4a4f55'))
    if r.random() < .22 and (s := spot(a1)):                # 물탱크
        tc = r.choice(['#e8b62c', '#e8b62c', '#3f86c9', '#d9d9d2'])
        for dx, dy in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)): mb.box((s[0] + dx, s[1] + dy, h), .06, .06, .7, mat_flat('#5a5a58'))
        mb.cyl((s[0], s[1], h + .7), .75, 1.3, mat_flat(tc), mat_flat('#f2efe4' if tc != '#d9d9d2' else '#b9b9b2'))
    for _ in range(r.randrange(0, 4)):                      # 실외기
        if (s := spot(a1)): mb.box((s[0], s[1], h), .5, .25, .7, mat_flat('#e2e2dc'), ang + r.choice([0, math.pi / 2]), mat_flat('#bdbdb6'))
    if ar > 110 and r.random() < .13 and (s := spot(a2)):   # 태양광 판(남쪽으로 기울인 짙은 남색 판)
        for j in range(r.randrange(2, 5)): x, y = s[0] + j * 1.25 - 1.9, s[1]; mb.face([(x - .55, y - .9, h + .3), (x + .55, y - .9, h + .3), (x + .55, y + .9, h + 1.05), (x - .55, y + .9, h + 1.05)], mat_flat('#2f4a78'))
    if r.random() < .14 and (s := spot(a1)):                # 옥상 화분·텃밭
        for j in range(r.randrange(2, 5)): mb.box((s[0] + math.cos(ang) * j * 1.1, s[1] + math.sin(ang) * j * 1.1, h), .45, .3, .45, mat_flat('#8a6a4a'), ang, mat_flat('#5a9a45'))
    if r.random() < .15 and (s := spot(a1)): mb.box((s[0], s[1], h), .9, .6, .12, mat_flat('#8a6a4a'), ang)   # 평상
    if ar > 600: roof_kit(mb, poly, h, r, 1 + int(ar // 900))   # 큰 건물: 기계실·냉각탑
    mb.build('b%d' % idx, idx)

# ================= 아파트 동과 단지 =================
# 거리뷰에서 본 것: 새 단지는 밝은 회색·아이보리 벽에 짙은 회색·베이지 띠, 저층부는 석재, 발코니는 유리, 옥상에 기계실과 그 위를 덮는 장식 틀. 옛 단지(은마 등)는 크림색 벽에 벽돌색·파란 세로띠,
# 창틀이 굵은 발코니와 실외기, 초록 방수 옥상의 물탱크. 어느 쪽이든 옆벽(측벽) 위쪽에 동 번호가 크게 적혀 있다. 번호는 OSM 건물 이름에서 읽은 것이다(상표·단지 이름은 그리지 않는다).
APT_NEW = [dict(wall='#cfcdc8', acc='#5f646b', base='#8f8b85', glass='#44586b', fr='#e9e9e4', deck='#9a9c9e'), dict(wall='#eeebe2', acc='#b3a48c', base='#b5aa98', glass='#3f5568', fr='#ffffff', deck='#a5a39c'),
           dict(wall='#e9e7e1', acc='#7f95a8', base='#9aa3aa', glass='#3f5568', fr='#ffffff', deck='#a5a39c'), dict(wall='#d9d2c5', acc='#7b6654', base='#8a7a69', glass='#44525c', fr='#efe9dc', deck='#9d9c96'),
           dict(wall='#e6e6e2', acc='#4f7f86', base='#8f9a9c', glass='#3f5568', fr='#ffffff', deck='#9a9c9e')]
APT_OLD = [dict(wall='#e9e2cf', acc='#a8553f', base='#cfc6ae', glass='#4a5f70', fr='#f4f1e8', deck='#63ad8c'), dict(wall='#e4e2da', acc='#4f79a8', base='#c9c7bf', glass='#4a5f70', fr='#f6f5f0', deck='#5ba684'),
           dict(wall='#dccfb4', acc='#8a6a4e', base='#c4b79c', glass='#4a5f70', fr='#f4efe2', deck='#9d9c96'), dict(wall='#dfe3da', acc='#5c8f6e', base='#c5cabf', glass='#4a5f70', fr='#f6f5f0', deck='#63ad8c')]
APM, ABAY, AFL = 28, 3.6, 2.9
def apt_scheme(cx, seed, lv):
    era = cx['era'] if cx else ('old' if lv <= 15 else 'new'); L_ = APT_OLD if era == 'old' else APT_NEW; i = random.Random(cx['seed'] if cx else seed).randrange(len(L_)); return era, f'{era}{i}', L_[i]
def apt_face(key, sch, era):
    """앞·뒤 입면(발코니 쪽) 그림: 4칸 × 2층, 칸 3.6 m, 층 2.9 m."""
    bw, fh = int(ABAY * APM), int(AFL * APM); wall, acc, glass, fr = sch['wall'], sch['acc'], sch['glass'], sch['fr']
    def draw(d):
        rnd = random.Random(zlib.crc32(key.encode())); g2 = shade(glass, 1.4)
        for f in range(2):
            for b_ in range(4):
                ox, oy = b_ * bw, f * fh
                if era == 'new':
                    if b_ == 3: d.rectangle([ox, oy, ox + 24, oy + fh], fill=acc); x0, x1 = 40, bw - 14
                    elif b_ == 1: x0, x1 = 22, bw - 22
                    else: x0, x1 = 8, bw - 8
                    d.rectangle([ox + x0 - 2, oy + 14, ox + x1 + 2, oy + fh - 16], fill=fr); d.rectangle([ox + x0, oy + 16, ox + x1, oy + fh - 18], fill=glass)
                    d.polygon([(ox + x0, oy + fh - 18), (ox + x0, oy + 40), (ox + x0 + 30, oy + 16)], fill=g2)
                    for k in range(1, 3 if b_ != 1 else 2): xx = x0 + (x1 - x0) * k // (3 if b_ != 1 else 2); d.line([(ox + xx, oy + 16), (ox + xx, oy + fh - 18)], fill=fr, width=2)
                    if b_ in (0, 2): d.rectangle([ox + x0, oy + fh - 34, ox + x1, oy + fh - 18], fill=shade(glass, 1.25)); d.line([(ox + x0, oy + fh - 34), (ox + x1, oy + fh - 34)], fill=fr, width=2)   # 유리 난간
                else:
                    if b_ == 3: d.rectangle([ox + 34, oy, ox + 66, oy + fh], fill=acc); d.rectangle([ox + 42, oy + 20, ox + 58, oy + 44], fill=glass); continue   # 계단실 세로띠
                    d.rectangle([ox + 3, oy + 12, ox + bw - 4, oy + fh - 24], fill=fr)
                    for k in range(4):
                        xa = ox + 6 + k * (bw - 12) // 4; xb = ox + 6 + (k + 1) * (bw - 12) // 4 - 3; d.rectangle([xa, oy + 15, xb, oy + fh - 27], fill=(glass if rnd.random() > .28 else rnd.choice(['#c9c6b8', '#8a97a3', '#b8b29e'])))
                    d.rectangle([ox + 2, oy + fh - 24, ox + bw - 3, oy + fh - 6], fill=shade(wall, .94)); d.line([(ox + 2, oy + fh - 15), (ox + bw - 3, oy + fh - 15)], fill=shade(wall, .8))
                    if b_ == 2 or (b_ == 0 and f == 1): d.rectangle([ox + 60, oy + fh - 22, ox + 82, oy + fh - 8], fill='#e4e4de', outline='#9a9a94')   # 실외기
            d.rectangle([0, f * fh + fh - 3, bw * 4, f * fh + fh], fill=shade(wall, .86))
    return _png('aptf_' + key, bw * 4, fh * 2, wall, draw), ABAY * 4, AFL * 2
def apt_gable(key, sch, era):
    """옆벽(측벽) 그림: 벽 너비 전체에 한 장(가로는 늘어난다), 2층. 가운데 작은 창 한 줄."""
    fh = int(AFL * APM); wall, glass, fr = sch['wall'], sch['glass'], sch['fr']
    def draw(d):
        for f in range(2):
            d.rectangle([0, f * fh + fh - 2, 200, f * fh + fh], fill=shade(wall, .9)); d.rectangle([88, f * fh + 20, 112, f * fh + 52], fill=fr); d.rectangle([90, f * fh + 22, 110, f * fh + 50], fill=glass)
        if era == 'old': d.rectangle([150, 0, 172, fh * 2], fill=shade(wall, .93))
    return _png('aptg_' + key, 200, fh * 2, wall, draw), AFL * 2
def apt_base(key, sch):
    """새 단지 저층부(2개 층): 석재 + 짙은 필로티·출입구."""
    def draw(d):
        for b_ in range(4):
            ox = b_ * 100; d.line([(ox, 0), (ox, 162)], fill=shade(sch['base'], .85)); d.line([(0, 81), (400, 81)], fill=shade(sch['base'], .85))
            if b_ % 2 == 0: d.rectangle([ox + 16, 86, ox + 84, 162], fill='#34383e'); d.rectangle([ox + 16, 86, ox + 84, 92], fill=sch['acc'])
            d.rectangle([ox + 30, 18, ox + 70, 56], fill=sch['glass'])
    return _png('aptb_' + key, 400, 162, sch['base'], draw), ABAY * 4, 5.8
def apartment(b, idx):
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = b['h']; cx = S['complexes'][b['cx']] if b.get('cx') is not None and S.get('complexes') else None; era, key, sch = apt_scheme(cx, b['seed'], b['lv']); new = era == 'new'
    fp, ftw, fth = apt_face(key, sch, era); fm = mat_tex(fp, 'af_' + key); gp, gth = apt_gable(key, sch, era); gm = mat_tex(gp, 'ag_' + key); wallm, accm = mat_flat(sch['wall']), mat_flat(sch['acc'])
    c, ax_, Lx, Ly, _ = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); mb = MB(); zb = 5.8 if (new and h > 30) else 0.0; rnd = random.Random(b['seed']); s = 0.0
    for ring in [poly.exterior] + list(poly.interiors):
        for seq in ring_runs(list(ring.coords)):
            ar = _arc(seq); L = ar[-1]; d = np.subtract(seq[-1], seq[0]); par = abs(float(d @ ax_)) / (np.hypot(*d) or 1)
            kind = 'g' if (par < .5 and L >= 6.5 and len(seq) == 2 and ring is poly.exterior) else 'f' if L >= 3.2 else 'p'
            for k in range(len(seq) - 1):
                a, q = seq[k], seq[k + 1]
                if ar[k + 1] - ar[k] < 1e-4: continue
                u0, u1, m, vt = ((s + ar[k]) / ftw, (s + ar[k + 1]) / ftw, fm, fth) if kind == 'f' else (ar[k] / L, ar[k + 1] / L, gm, gth) if kind == 'g' else (0, 0, wallm, 1)
                mb.face([(a[0], a[1], zb), (q[0], q[1], zb), (q[0], q[1], h), (a[0], a[1], h)], m, [(u0, zb / vt), (u1, zb / vt), (u1, h / vt), (u0, h / vt)])
            s += L
    if zb: bp_, btw, bth = apt_base(key, sch); skin(mb, poly, 0.0, lambda x, y: zb, mat_tex(bp_, 'ab_' + key), btw, bth)
    if b.get('no'):   # 동 번호: 옆벽(긴 축에 수직인 벽)을 먼저, 없으면 긴 벽에. 카메라 쪽을 보는 벽을 앞세워 두 군데까지
        cc = list(poly.exterior.coords); ed = []
        for p0, p1 in zip(cc[:-1], cc[1:]):
            p0, p1 = np.array(p0), np.array(p1); L = float(np.hypot(*(p1 - p0)))
            if L < 5.5: continue
            e = (p1 - p0) / L; n_ = np.array([e[1], -e[0]]); ed.append((abs(float(e @ ax_)) < .5, float(n_ @ VD[:2]) < -.15, L, p0, e, n_))
        if not any(g_[0] for g_ in ed) and len(ed) > 2: ed = sorted(ed, key=lambda g_: -g_[2])[1:]   # 옆벽이 없는 탑상형: 가장 긴 벽(주 입면)은 비워 둔다
        npth, asp = sign_png(f"apt_{b['no']}_{key}", b['no'], shade(sch['acc'], .8 if new else 1.0), sch['wall'], SANS, pad=.12, mx=.15); nm_ = mat_tex(npth, f"an_{b['no']}_{key}")
        for gab, vis, L, p0, e, n_ in sorted(ed, key=lambda g_: (not g_[1], not g_[0], -g_[2]))[:2]:
            hh = min(4.6, L * .75 / asp); w = hh * asp; m0 = p0 + e * L / 2 + n_ * .07; z0_ = h - (5.0 if new else 2.6) - hh
            if z0_ < zb + 3: continue
            q0, q1 = m0 - e * w / 2, m0 + e * w / 2; mb.face([(*q0, z0_), (*q1, z0_), (*q1, z0_ + hh), (*q0, z0_ + hh)], nm_, [(0, 0), (1, 0), (1, 1), (0, 1)])
    capf(mb, poly, lambda x, y: h, mat_flat(sch['deck'])); inner = poly.buffer(-0.35, join_style=2)
    if inner.geom_type == 'Polygon' and inner.area > 8:
        for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms: mb.face([(x, y, h + .9) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], wallm)
        for ring, fl in ((poly.exterior, False), (inner.exterior, True)):
            cc = list(ring.coords)
            for a_, q in zip(cc[:-1], cc[1:]): pts = [(a_[0], a_[1], h), (q[0], q[1], h), (q[0], q[1], h + .9), (a_[0], a_[1], h + .9)]; mb.face(pts[::-1] if fl else pts, wallm)
    if new: cb = orient(poly.buffer(.12, join_style=2), 1.0); skin(mb, cb, h - 3.0, lambda x, y: h + .95, accm, 1, 1)   # 꼭대기 층 띠
    ang = math.atan2(ax_[1], ax_[0]); ncore = max(1, int(Lx // 20)); safe = poly.buffer(-1.8); tops = []; hy = min(2.4, Ly * .32)
    for k in range(ncore):   # 승강기 기계실(옥탑)
        p_ = c + ax_ * ((k + .5) / ncore - .5) * Lx * .8
        if not safe.contains(Point(*p_)): continue
        hb = 4.4 if new else 3.2; mb.box((p_[0], p_[1], h), 2.6, hy, hb, wallm, ang, mat_flat('#8f8e88')); tops.append(p_)
        if new: obox(mb, p_, ax_, 3.3, hy + .7, h + hb, h + hb + .35, accm)   # 기계실 위 장식 판
        elif rnd.random() < .7: tc = rnd.choice(['#e8b62c', '#3f86c9', '#e9e9e4']); mb.cyl((p_[0], p_[1], h + hb), .95, 1.25, mat_flat(tc), mat_flat('#f2efe4'), n=10)   # 물탱크
    if new and len(tops) >= 2:   # 기계실을 잇는 옥상 장식 틀
        for p0, p1 in zip(tops[:-1], tops[1:]):
            for sv in (-1, 1): beam(mb, (*(p0 + nv * sv * (hy + .4)), h + 4.58), (*(p1 + nv * sv * (hy + .4)), h + 4.58), .32, accm)
    for _ in range(rnd.randrange(1, 4)):   # 환기구
        t_ = rnd.uniform(-.4, .4); p_ = c + ax_ * t_ * Lx + nv * rnd.uniform(-.25, .25) * Ly
        if safe.contains(Point(*p_)): mb.box((p_[0], p_[1], h), .45, .45, .6, mat_flat('#d9d9d2'), ang, mat_flat('#8f8e88'))
    mb.build('b%d' % idx, idx)
# 단지 둘레의 생울타리 담과 정문(문주). 담은 차도가 경계를 넘는 곳마다 끊는다. 문주의 생김새(기둥 둘 + 보, 옆의 경비실)는 거리뷰의 여러 단지에서 본 꼴을 단순화한 것이다.
for _ci, _cx in enumerate(S.get('complexes', [])):
    _p = P(_cx['rings']); _cen = _p.centroid.coords[0]
    if _p.is_empty or not inwin(_cen, 8, max(Point(_cen).distance(Point(q)) for q in _p.exterior.coords) + 12): continue
    _era, _key, _sch = apt_scheme(_cx, 0, _cx['lv']); mb = MB(); _in = _p.buffer(-.8)
    _ring = (_in if _in.geom_type == 'Polygon' else _p).exterior.difference(unary_union([Point(g[0], g[1]).buffer(max(5.0, g[3] / 2 + 2.6)) for g in _cx['gates']] + [Point(0, 0).buffer(.01)]))
    for ln in ([_ring] if _ring.geom_type == 'LineString' else [g for g in getattr(_ring, 'geoms', []) if g.geom_type == 'LineString']):
        if ln.length < 3: continue
        for q in parts(ln.buffer(.38, cap_style=2)):
            q = orient(q, 1.0); skin(mb, q, 0.0, lambda x, y: .5, mat_flat(_sch['base']), 1, 1); skin(mb, q, .5, lambda x, y: 1.5, mat_flat('#4f8f3f'), 1, 1); capf(mb, q, lambda x, y: 1.5, mat_flat('#5a9a45'))
    for gx, gy, ga, gw, main in _cx['gates']:
        if not main: continue
        nrm = np.array([-math.sin(ga), math.cos(ga)]); g0 = np.array([gx, gy]); hw = gw / 2 + 1.5
        for sv in (-1, 1): p_ = g0 + nrm * sv * hw; mb.box((p_[0], p_[1], 0), .75, .75, 6.4, mat_flat(_sch['base']), ga, mat_flat(shade(_sch['base'], .85)))
        obox(mb, g0, nrm, hw + 1.6, .9, 5.5, 6.5, mat_flat(_sch['acc']), mat_flat(shade(_sch['acc'], .85))); q_ = g0 + nrm * (hw + 3.0); mb.box((q_[0], q_[1], 0), 1.3, 1.3, 2.7, mat_flat(_sch['wall']), ga, mat_flat('#8f8e88'))
    if mb.f: mb.build('cxw%d' % _ci, 9800 + _ci); META[9800 + _ci] = 'landmark:apt_grounds'

# ================= 45 m 이상 일반 타워 =================
# 테헤란로 북쪽 변을 150 m 간격으로 본 유형: 청록·파란 유리 커튼월, 흰 띠와 유리가 번갈아 도는 띠창, 석재 격자에 네모 창, 짙은 유리 + 검은 멀리언, 세로 석재 핀. 유형은 건물마다 고정 난수로 나눈다.
TGL = ['#5f9aa0', '#6fa4a6', '#5d8fbf', '#6f9cc0', '#4f8a8c', '#7d93a6', '#6c8197', '#74b0bf']
TSTONE = [('#e6e4dc', '#39485a'), ('#cfc8ba', '#34444f'), ('#d8c9ae', '#3a4651'), ('#b9b6ae', '#2f3d49'), ('#8d8a84', '#27323b'), ('#f0eee8', '#3d5166')]
def stone_tex(key, wall, win, bay=3.6, flh=3.9):
    """석재 격자 입면: 칸마다 네모 창 둘(움푹한 짙은 유리)."""
    def draw(d):
        bp, fp = bay * RPPM, flh * RPPM
        for f in range(2):
            for b_ in range(4):
                x0, y0 = int(b_ * bp), int(f * fp)
                for k in range(2): xa = x0 + int(bp * (.08 + k * .5)); d.rectangle([xa - 2, y0 + int(fp * .2) - 2, xa + int(bp * .36) + 2, y0 + int(fp * .78) + 2], fill=shade(wall, .78)); d.rectangle([xa, y0 + int(fp * .2), xa + int(bp * .36), y0 + int(fp * .78)], fill=win)
            d.line([(0, int(f * fp)), (int(bp * 4), int(f * fp))], fill=shade(wall, .86), width=2)
    return _png('stone_' + key, int(bay * 4 * RPPM), int(flh * 2 * RPPM), wall, draw), bay * 4, flh * 2
def diagrid_tex(glass, frame):
    """사선 격자(다이아그리드): 8 × 16 m 마름모가 되풀이된다."""
    def draw(d):
        w, h = int(8 * RPPM), int(16 * RPPM)
        for y in range(0, h, int(4 * RPPM)): d.line([(0, y), (w, y)], fill=shade(glass, .86), width=2)
        for x in range(0, w, int(2 * RPPM)): d.line([(x, 0), (x, h)], fill=shade(glass, .92))
        for a, b_ in (((0, 0), (w, h)), ((w, 0), (0, h))): d.line([a, b_], fill=frame, width=int(.55 * RPPM))
    return _png(f'diag_{glass}', int(8 * RPPM), int(16 * RPPM), glass, draw), 8.0, 16.0
# 거리뷰에서 글자를 읽은 간판(2026-07 촬영분, 테헤란로를 150 m 간격으로 지나며 북쪽 변 건물 꼭대기를 확대해 본 276장을 문자 인식으로 추리고 눈으로 확인했다). 글꼴은 일반 글꼴이고 상표 도안은 그리지 않는다.
#   OSM id → (글자, 글자색, 바탕색, 글꼴, 간판이 보는 길, 자리): crown 꼭대기 띠 / low 저층부 / vert 꼭대기 모서리의 세로 간판 / box 옥상 위에 세운 판
TOWER_SIGNS = {
    'w557469309': ('workflex', '#f6f5f0', '#3a3d42', SANS, '테헤란로', 'low'),            # 강남N타워 저층부의 흰 글자
    'w561726162': ('KR TOWER', '#d0282e', '#5d8fbf', SANS, '테헤란로', 'vert'),           # 파란 유리 타워 꼭대기의 붉은 세로 글자
    'w272052332': ('ARTNOUVEAU CITY HOTEL', '#c9a24c', '#3f4247', SERIF, '테헤란로', 'crown'),   # 역삼아르누보호텔: 짙은 꼭대기 띠의 금색 글자
    'w703780988': ('FASTFIVE', '#3c3f44', '#b9b6ae', SANS, '테헤란로', 'crown'),          # 회색 석재 꼭대기 띠의 짙은 글자
    'w800238998': ('HOTEL PEYTO', '#f6f5f0', '#9a9c9a', SANS, '테헤란로', 'crown'),       # 회색 호텔 꼭대기의 흰 글자
    'w547175590': ('MEGABOX', '#5a4fb0', '#d8d2c4', SANS, '강남대로', 'low'),             # 강남역 스타플렉스 저층부 석재 벽의 보라색 글자
    'w471384881': ('Canon', '#d0282e', '#f6f5f0', SANS, '테헤란로', 'box'),               # 캐논타워 옥상의 흰 판 + 붉은 글자
    'w557469316': ('SPARKPLUS', '#5fa8c8', '#f0eee8', SANS, '테헤란로', 'crown'),         # 흰 석재 격자 건물 꼭대기
}
# 거리뷰에서 외장을 본 건물의 유형·색(나머지는 고정 난수). sty = 유형, g = 유리색, st = (석재색, 창색), spc = 띠 색
TOWER_STYLE = {
    'w845329553': dict(sty='diagrid'),                                   # 선릉역 서쪽 테헤란로 북쪽 변의 사선 격자 유리 건물
    'w557469309': dict(sty='dark', g='#3f4a56'), 'w561726162': dict(sty='curtain', g='#5d8fbf'), 'w272052332': dict(sty='stone', st=('#55585d', '#c9ccd0')),
    'w703780988': dict(sty='stone', st=('#b9b6ae', '#2f3d49')), 'w800238998': dict(sty='stone', st=('#cfcfca', '#34444f')), 'w547175590': dict(sty='fins', g='#5d8fbf', st=('#e6e4dc', '#4f7fb5')),
    'w471384881': dict(sty='curtain', g='#5f9aa0'), 'w557469316': dict(sty='stone', st=('#f0eee8', '#3d5166')), 'w1078788212': dict(sty='band', g='#6f9cc0', spc='#d8c9ae'),   # 빅토리아오피스텔: 베이지 석재 띠 + 파란 띠창
}
def vsign_png(path):
    """세로 간판: 가로 글자 그림을 시계 방향으로 돌린다(위에서 아래로 읽힌다)."""
    p = path[:-4] + '_v.png'
    if not os.path.exists(p): Image.open(path).rotate(-90, expand=True).save(p)
    return p
_tower_base = tower
def tower(b, idx, cfg=None):
    if cfg is not None: return _tower_base(b, idx, cfg)
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = b['h']; r = random.Random(b['seed'] * 31 + 7); mb = MB(); c, ax_, Lx, Ly, mc = mrr_axes(poly); resi = b['kind'] in ('resi_tower', 'officetel', 'hotel', 'apartments', 'residential', 'dormitory')
    ov = TOWER_STYLE.get(b['osm'], {}); sty = ov.get('sty') or (_pick(r, [('band', 5), ('stone', 3), ('curtain', 2)]) if resi else _pick(r, [('curtain', 30), ('band', 22), ('stone', 22), ('dark', 13), ('fins', 13)]))
    flh = 3.3 if resi else r.choice([3.9, 4.0, 4.2]); g = r.choice(TGL); sw, sg = r.choice(TSTONE); g = ov.get('g', g); sw, sg = ov.get('st', (sw, sg))
    if sty == 'curtain': sp = r.choice([.1, .14, .2]); path, tw, th = grid_tex(f'tc{g}{sp}{flh}', g, shade(g, .6), 1.5, flh, sp=sp); span = shade(g, .8)
    elif sty == 'dark': g = ov.get('g') or r.choice(['#3f4a56', '#2f3a45', '#4b5661', '#3a4a4f']); path, tw, th = grid_tex(f'td{g}{flh}', g, shade(g, .55), 1.2, flh, sp=.1); span = shade(g, .8)
    elif sty == 'band': spc = r.choice(['#e6e8e6', '#d8dcdc', '#cfc8ba', '#e9e2d0', '#c9cfd4']); spc = ov.get('spc', spc); path, tw, th = grid_tex(f'tb{g}{spc}{flh}', g, shade(g, .6), 1.6, flh, sp=.42, spc=spc); span = spc
    elif sty == 'diagrid': g = '#86a8c8'; path, tw, th = diagrid_tex(g, '#4a5560'); span = '#4a5560'
    elif sty == 'fins': path, tw, th = finwall_tex(f'tf{sw}{sg}{flh}', sw, sg, shade(sw, 1.06), bay=r.choice([1.8, 2.4]), flh=flh, finw=.5); span = sw
    else: path, tw, th = stone_tex(f'{sw}{sg}{flh}', sw, sg, flh=flh); span = sw
    m = mat_tex(path, 'tw_' + path); LB = 8.0 if h >= 60 else 4.4; _lobby(mb, poly, LB, g if sty not in ('stone', 'fins') else sg, span, shade(g, .5))
    skin(mb, poly, LB, lambda x, y: h, m, tw, th); capf(mb, poly, lambda x, y: h, mat_flat('#9a9c9e')); _parapet(mb, poly, h, span)
    up_ = None; cr_ = poly.buffer(-min(4.0, 0.18 * Ly), join_style=2); core = poly.buffer(-max(2.5, 0.28 * Ly), join_style=2)
    if r.random() < .4 and cr_.geom_type == 'Polygon' and cr_.area > 30:   # 한 단 들어간 꼭대기
        hz = min(9.0, 0.05 * h + 3); skin(mb, orient(cr_, 1.0), h, lambda x, y: h + hz, m, tw, th); capf(mb, cr_, lambda x, y: h + hz, mat_flat('#8f9296')); up_ = (cr_, h + hz)
    elif core.geom_type == 'Polygon' and core.area > 15: skin(mb, orient(core, 1.0), h, lambda x, y: h + 4.5, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: h + 4.5, mat_flat('#8c8e90')); up_ = (core, h + 4.5)
    heli = h >= 100 and up_ is not None
    if heli: heli_std(mb, c, ax_, up_[1], Ly, r)
    roof_std(mb, poly, h, up_[0] if up_ else None, up_[1] if up_ else h, heli, b['seed'])
    sg_ = TOWER_SIGNS.get(b['osm'])
    if sg_:
        text, fg, bg, fonts, road, mode = sg_; pth, asp = sign_png('tw_' + b['osm'], text, fg, bg, fonts, track=.08); dv = np.array(_toward_road(poly, road), float); dv /= np.hypot(*dv); side = np.array([-dv[1], dv[0]])
        if mode == 'vert': hs = min(18.0, h * .28); wall_strip(mb, poly, dv, h - 1.5 - hs, h - 1.5, mat_tex(vsign_png(pth), 'sgv_' + b['osm']), w=hs / asp, off=.4, org=np.array(c) + side * Ly * .22)
        elif mode == 'low': wall_strip(mb, poly, dv, 13.0, 17.4, mat_tex(pth, 'sg_' + b['osm']), aspect=asp, off=.5)
        elif mode == 'box': wall_strip(mb, poly, dv, h + .9, h + 5.6, mat_tex(pth, 'sg_' + b['osm']), aspect=asp, off=.12); wall_strip(mb, poly, dv, h + .5, h + 5.9, mat_flat('#c9cbc8'), w=4.7 * asp + .8, off=-.15)
        else: wall_strip(mb, poly, dv, h - 4.4, h - .5, mat_tex(pth, 'sg_' + b['osm']), aspect=asp, off=.4)
    toonify(mb.build('b%d' % idx, idx))

def ltower(b, idx, cfg):
    """랜드마크 유리 타워: 공용 gtower 와 같은 입면(cfg)에, 일반 타워와 같은 옥상(바닥 색 구획·턱·냉각탑·기계실, 100 m 이상은 헬리패드)을 얹는다. 옥상 배치는 건물마다 맞춘 것이 아니다."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = cfg.get('hroof') or b['h']; mb = MB(); LB = cfg.get('lobby', 8.0); r = random.Random(b['seed']); pc = cfg.get('spc') or shade(cfg['glass'], .8)
    key = f"{cfg['glass']}_{cfg.get('spc')}_{cfg.get('sp', 0)}_{cfg.get('flh', 4.0)}_{cfg.get('bay', 1.5)}"
    path, tw, th = grid_tex(key, cfg['glass'], cfg['line'], cfg.get('bay', 1.5), cfg.get('flh', 4.0), sp=cfg.get('sp', 0.0), spc=cfg.get('spc'), var=cfg.get('var', .04)); gm = mat_tex(path, 'g' + key)
    if LB: _lobby(mb, poly, LB, cfg['glass'], pc, cfg['line'])
    skin(mb, poly, LB, lambda x, y: h, gm, tw, th); capf(mb, poly, lambda x, y: h, mat_flat('#9a9c9e')); _parapet(mb, poly, h, pc)
    if cfg.get('crownband'): cb = orient(poly.buffer(.3, join_style=2), 1.0); skin(mb, cb, h - cfg['crownband'], lambda x, y: h + 1.3, mat_flat(pc), 1, 1)
    c, ax_, Lx, Ly, _ = mrr_axes(poly); core = poly.buffer(-max(3.0, 0.26 * Ly), join_style=2); up_ = None
    if core.geom_type == 'Polygon' and core.area > 15: skin(mb, orient(core, 1.0), h, lambda x, y: h + 4.5, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: h + 4.5, mat_flat('#8c8e90')); up_ = (core, h + 4.5)
    heli = h >= 100 and up_ is not None and core.area > 500
    if heli: heli_std(mb, c, ax_, up_[1], Ly, r)
    roof_std(mb, poly, h, up_[0] if up_ else None, up_[1] if up_ else h, heli, b['seed'])
    toonify(mb.build('b%d' % idx, idx))
LMB.update({k: ltower for k in ('trade', 'asem', 'parnas', 'gfc', 'samsung_e', 'samsung_c', 'samsung_l', 'cf_e', 'cf_w', 'meritz', 'glass')})   # GS타워는 옥상 원통 간판이 있어 그대로 둔다

# ================= 포스코센터 =================
def posco(b, idx, cfg):
    """포스코센터(거리뷰 대조: 테헤란로 정면, 동·서·남쪽). 청록 유리 타워 두 동(동관이 높다) 사이에 낮은 유리 아트리움이 있고, 타워마다 아트리움 쪽 앞 모서리에 회색 석재 세로 기둥(코어)이 지붕 위까지 오른다.
    유리는 가는 격자에 층마다 밝은 가로선. OSM 윤곽은 뒤쪽 저층부까지 한 덩어리라, 테헤란로 쪽 앞부분만 타워로 세우고 뒤는 저층부로 낮췄다(타워 깊이 52·55 m, 저층부·아트리움 높이 24·27 m 는 사진 비례로 잡은 추정).
    동관 꼭대기의 흰 'posco' 는 북·동쪽에서 읽었다. 남·서쪽 면은 확인하지 못해 넣지 않았다."""
    poly = orient(P(b['rings']), 1.0); east = b['osm'] == 'w840263996'; H = b['h']; mb = MB(); c, ax_, Lx, Ly, _ = mrr_axes(poly); c = np.array(c)
    f = np.array(_toward_road(poly, '테헤란로'), float); f /= np.hypot(*f); nv = np.array([-ax_[1], ax_[0]]); d, D, wv, Wd = (ax_, Lx / 2, nv, Ly / 2) if abs(ax_ @ f) > .7 else (nv, Ly / 2, ax_, Lx / 2)
    d = d if d @ f > 0 else -d; ob = next((x for x in S['buildings'] if x['osm'] == ('w466291216' if east else 'w840263996')), None); oc = np.array(P(ob['rings']).centroid.coords[0]) if ob else c + wv * 60
    wv = wv if wv @ (oc - c) > 0 else -wv; TD = 52.0 if east else 55.0
    front = Polygon([tuple(c + d * a_ + wv * s_ * 400) for a_, s_ in ((D - TD, -1), (D + 50, -1), (D + 50, 1), (D - TD, 1))]); tw_ = orient(max(parts(poly.intersection(front)), key=lambda q: q.area), 1.0); rear = poly.difference(front)
    path, gw, gh = grid_tex('posco', cfg['glass'], cfg['line'], 1.5, 4.1, sp=.14, spc='#9cc4c2'); gm = mat_tex(path, 'gposco'); _lobby(mb, tw_, 10.0, cfg['glass'], '#cfd6d6', cfg['line'])
    skin(mb, tw_, 10.0, lambda x, y: H, gm, gw, gh); capf(mb, tw_, lambda x, y: H, mat_flat('#9a9c9e')); _parapet(mb, tw_, H, '#b9c4c4')
    cb = orient(tw_.buffer(.25, join_style=2), 1.0); skin(mb, cb, H - 4.6, lambda x, y: H + 1.3, mat_flat(shade(cfg['glass'], .72)), 1, 1)   # 꼭대기 짙은 띠
    core = tw_.buffer(-9.0, join_style=2)
    if core.geom_type == 'Polygon' and core.area > 30: skin(mb, orient(core, 1.0), H, lambda x, y: H + 5.0, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: H + 5.0, mat_flat('#8c8e90'))
    tc_, tax, tLx, tLy, _m = mrr_axes(tw_)
    if east and core.geom_type == 'Polygon': heli_std(mb, tc_, tax, H + 5.0, tLy, random.Random(5))
    roof_std(mb, tw_, H, core if core.geom_type == 'Polygon' else None, H + 5.0, east, b['seed'])
    sp_ = c + d * (D - 5.5) + wv * (Wd - 1.2); obox(mb, sp_, d, 5.0, 2.2, 0.0, H + 4.5, mat_flat('#b9b5aa'), mat_flat('#a3a096'))   # 아트리움 쪽 앞 모서리의 석재 세로 기둥
    for z_ in np.arange(12.0, H, 8.2): obox(mb, sp_, d, 5.06, 2.26, z_, z_ + .35, mat_flat('#9d998f'))
    for q in parts(rear):   # 뒤쪽 저층부: 석재 띠 + 유리
        if q.area < 40: continue
        q = orient(q, 1.0); pp, pw, ph = grid_tex('posco_pod', '#7fa9aa', cfg['line'], 3.0, 4.8, sp=.34, spc='#d0d2cc'); skin(mb, q, 0.0, lambda x, y: 24.0, mat_tex(pp, 'gposcop'), pw, ph); flat_roof(mb, q, 24.0, '#d0d2cc', '#a9aca6')
        roof_kit(mb, q, 24.0, random.Random(b['seed']), 2 + int(q.area // 700))
    if east and ob is not None:   # 두 동 사이 아트리움: 유리 상자 + 흰 틀 + 둥근 유리 지붕
        op = P(ob['rings']); gap = unary_union([poly, op]).convex_hull.difference(poly.buffer(.3)).difference(op.buffer(.3)).intersection(Polygon([tuple(c + d * a_ + wv * s_ * 400) for a_, s_ in ((D - 46, -1), (D - 4, -1), (D - 4, 1), (D - 46, 1))]))
        gs = [q for q in parts(gap) if q.area > 150]
        if gs:
            at = orient(max(gs, key=lambda q: q.area), 1.0); ap, aw, ah = grid_tex('posco_at', '#8fc2c2', cfg['line'], 2.4, 4.5, sp=.08, spc='#e6eeee'); skin(mb, at, 0.0, lambda x, y: 27.0, mat_tex(ap, 'gposcoa'), aw, ah)
            ac, aax, aLx, aLy, _m = mrr_axes(at); anv = np.array([-aax[1], aax[0]]); N = 8; capf(mb, at, lambda x, y: 27.0, mat_flat('#9fc9cc'))
            prof = [(aLy * .46 * math.cos(math.pi * k / N), 27.0 + 5.5 * math.sin(math.pi * k / N)) for k in range(N + 1)]; clip = at.buffer(-.4)
            for (v0, z0), (v1, z1) in zip(prof[:-1], prof[1:]):   # 둥근 지붕(긴 축을 따라)
                a0, a1 = ac - aax * aLx * .46, ac + aax * aLx * .46
                if clip.contains(Point(*(a0 + anv * v0))) and clip.contains(Point(*(a1 + anv * v1))): mb.face([(*(a0 + anv * v1), z1), (*(a1 + anv * v1), z1), (*(a1 + anv * v0), z0), (*(a0 + anv * v0), z0)], mat_flat('#a9d0d6'))
            for s_ in np.linspace(-aLx * .46, aLx * .46, 9):
                for (v0, z0), (v1, z1) in zip(prof[:-1], prof[1:]):
                    p0 = ac + aax * s_
                    if clip.contains(Point(*(p0 + anv * v0))) and clip.contains(Point(*(p0 + anv * v1))): beam(mb, (*(p0 + anv * v0), z0 + .05), (*(p0 + anv * v1), z1 + .05), .3, mat_flat('#eef2f2'))
    if east:
        pth, asp = sign_png('posco', 'posco', '#f6f5f0', shade(cfg['glass'], .72), SANS, track=.06); m_ = mat_tex(pth, 'sg_posco')
        for dv in (d, -wv): wall_strip(mb, tw_, dv, H - 4.3, H + .9, m_, aspect=asp, off=.5)
    toonify(mb.build('b%d' % idx, idx))
LMB.update(posco_e=posco, posco_w=posco)
