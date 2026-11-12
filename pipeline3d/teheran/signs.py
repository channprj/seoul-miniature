# 랜드마크 간판. lm_build.py 끝에서 exec 로 읽는다(같은 전역: MB, mat_tex, mat_flat, toonify, inwin, S, TEXD, META …).
# 네이버 지도 거리뷰(2026-07 촬영분)에서 글자를 읽을 수 있었던 간판만 넣었다. 사진은 저장소에 넣지 않았다.
#   파르나스타워: 꼭대기 짙은 띠의 흰 세리프 'PARNAS' — 남·동·북쪽에서 본 면마다 있어 네 면 모두에 둔다
#   글라스타워: 흰 둥근 꼭대기 띠의 짙은 세리프 'GLASS TOWER' — 삼성역 사거리(북) 쪽에서 확인
#   포스코센터 동관: 꼭대기의 흰 소문자 'posco' — 테헤란로(북) 쪽에서 확인
#   GS타워: 옥상 흰 원통 위를 두른 청록 띠의 흰 'GS' — 남·북 어느 쪽에서도 보인다
#   현대백화점 무역센터점: 테헤란로 쪽 벽 동쪽 끝의 세로 전광판, 벽 위쪽의 'HYUNDAI'
#   코엑스 아티움: 삼성역 사거리 쪽 모퉁이를 감싼 대형 전광판(케이팝 광장)
#   코엑스: 영동대로 쪽 유리벽의 흰 'coex'(거리뷰에서는 앞 두 글자만 보였다)
# 넣지 않은 곳: DB금융센터(동쪽 면 꼭대기에 흰 'DB' 가 있지만 접힌 유리면 모델에는 붙일 평면이 없다), 아셈타워·강남파이낸스센터·메리츠타워(글자를 읽지 못함),
#   트레이드타워(서·남쪽 면에는 없고 동쪽 꼭대기 글자는 읽지 못함), 삼성 서초사옥·GT타워·센터필드(본 면에는 간판이 없었다).
# 이 판의 카메라는 남남서쪽에서 보므로 북·동쪽 면의 간판(글라스타워, 포스코, 코엑스)과 파르나스타워에 가린 아티움 전광판은 그림에 나오지 않는다. 장면(.blend·GLB)에는 들어 있다.
# 글자는 그림(15.6 cm/px)에서 읽히도록 실제보다 1.3–1.6배 크게 잡았다. 전광판 화면은 광고가 아니라 색 무늬다. 상표 도안은 그리지 않고 글자만 넣는다.
from PIL import ImageFont
_FD = '/System/Library/Fonts/Supplemental/'
def _font(names, size):
    for n in names:
        try: return ImageFont.truetype(_FD + n, size)
        except OSError: pass
    return ImageFont.load_default(size=size)
SERIF, SANS, SANSI = ('Georgia Bold.ttf', 'Times New Roman Bold.ttf'), ('Arial Bold.ttf', 'Arial Black.ttf'), ('Arial Bold Italic.ttf', 'Arial Bold.ttf')
def sign_png(key, text, fg, bg, fonts=SANS, track=0.0, hpx=120, pad=.22, mx=.5):
    """글자 간판 그림 → (경로, 가로/세로 비). track = 글자 사이를 글자 높이의 몇 배로 띄울지, mx = 양옆 여백(글자 높이의 배수)."""
    p = f'{TEXD}/sign_{key}.png'; f = _font(fonts, int(hpx * (1 - 2 * pad))); tr = int(track * hpx)
    d0 = ImageDraw.Draw(Image.new('RGB', (8, 8))); ws = [d0.textbbox((0, 0), ch, font=f) for ch in text]; adv = [d0.textlength(ch, font=f) for ch in text]
    W_ = int(sum(adv) + tr * (len(text) - 1) + 2 * mx * hpx); a0, d1 = f.getmetrics()
    if not os.path.exists(p):
        im = Image.new('RGB', (W_, hpx), bg); d = ImageDraw.Draw(im); x = mx * hpx; y = (hpx - (a0 + d1)) / 2
        for ch, a_ in zip(text, adv): d.text((x, y), ch, font=f, fill=fg); x += a_ + tr
        im.save(p)
    return p, W_ / hpx
def wall_strip(mb, poly, dirv, z0, z1, mat, w=None, aspect=None, off=.35, step=.75, reps=1.0, org=None):
    """건물 윤곽을 따라 붙는 띠(간판·전광판). 중심에서 dirv 쪽으로 쏜 선이 윤곽과 만나는 점을 가운데로, 윤곽을 따라 폭 w(없으면 높이 × aspect)만큼.
    윤곽은 반시계 방향이라 밖에서 보면 왼쪽 → 오른쪽이다(글자가 바로 읽힌다). 모퉁이·곡면은 윤곽을 따라 감긴다. org = 선을 쏘는 자리(기본은 중심)."""
    ext = orient(poly, 1.0).exterior; c = np.array(poly.centroid.coords[0] if org is None else org, float); dv = np.array(dirv, float); dv /= np.hypot(*dv)
    hit = LineString([c, c + dv * 3000]).intersection(ext)
    if hit.is_empty: return
    pts_ = [hit] if hit.geom_type == 'Point' else [g for g in getattr(hit, 'geoms', []) if g.geom_type == 'Point']
    if not pts_: return
    q = max(pts_, key=lambda g: (g.x - c[0]) * dv[0] + (g.y - c[1]) * dv[1]); L_ = ext.length; s0 = ext.project(q); w = w or (z1 - z0) * aspect
    ts = list(np.arange(s0 - w / 2, s0 + w / 2, step)) + [s0 + w / 2]; ring = []
    for t in ts:
        a, b = ext.interpolate((t - .05) % L_), ext.interpolate((t + .05) % L_); tg = np.array([b.x - a.x, b.y - a.y]); n_ = np.hypot(*tg)
        p = ext.interpolate(t % L_); nrm = np.array([tg[1], -tg[0]]) / n_ if n_ > 1e-6 else dv
        ring.append((p.x + nrm[0] * off, p.y + nrm[1] * off, (t - ts[0]) / w * reps))
    for (x0_, y0_, u0), (x1_, y1_, u1) in zip(ring[:-1], ring[1:]): mb.face([(x0_, y0_, z0), (x1_, y1_, z0), (x1_, y1_, z1), (x0_, y0_, z1)], mat, [(u0, 0), (u1, 0), (u1, 1), (u0, 1)])
def screen_png(key, w, h, cols, seed):
    """전광판 화면: 비스듬한 색 띠 + 둥근 색 덩이(광고 그림이 아닌 무늬)."""
    p = f'{TEXD}/screen_{key}.png'
    if not os.path.exists(p):
        r_ = random.Random(seed); im = Image.new('RGB', (w, h), cols[0]); d = ImageDraw.Draw(im)
        u_ = min(w, h)
        for k in range(14): x = r_.randrange(-u_, w); bw = r_.randrange(u_ // 8, u_ // 3); y0_ = r_.randrange(0, h); hh = r_.randrange(u_ // 2, u_ * 2); d.polygon([(x, y0_ + hh), (x + bw, y0_ + hh), (x + bw + hh // 2, y0_), (x + hh // 2, y0_)], fill=r_.choice(cols))
        for k in range(9): x, y, rr_ = r_.randrange(w), r_.randrange(h), r_.randrange(u_ // 8, u_ // 3); d.ellipse([x - rr_, y - rr_, x + rr_, y + rr_], fill=r_.choice(cols))
        d.rectangle([0, 0, w - 1, h - 1], outline='#22272b', width=max(2, h // 40)); im.save(p)
    return p
_B = {b['osm']: b for b in S['buildings']}
def _bp(osm):
    b = _B.get(osm)
    if b is None: return None, None
    g = orient(P(b['rings']), 1.0); c = g.centroid.coords[0]
    return (b, g) if g.geom_type == 'Polygon' and inwin(c, b['h'] + 30, max(Point(c).distance(Point(q)) for q in g.exterior.coords) + 20) else (None, None)
def _toward_road(g, name):
    c = Point(g.centroid.coords[0]); ln = min((LineString(r['pts']) for r in S['roads'] if r['name'] == name), key=lambda l: l.distance(c)); q = ln.interpolate(ln.project(c)); return (q.x - c.x, q.y - c.y)
smb = MB()
b, g = _bp('w927603580')   # 파르나스타워: 네 면 꼭대기
if b:
    pth, asp = sign_png('parnas', 'PARNAS', '#f6f5f0', '#2f3a45', SERIF, track=.28); m_ = mat_tex(pth, 'sg_parnas'); _c, ax_, _lx, _ly, _ = mrr_axes(g); nv_ = np.array([-ax_[1], ax_[0]])
    for dv in (ax_, -ax_, nv_, -nv_): wall_strip(smb, g, dv, b['h'] - 7.2, b['h'] - 2.4, m_, aspect=asp, off=.45)
b, g = _bp('w85032873')    # 글라스타워: 삼성역 사거리 쪽 둥근 꼭대기 띠
if b:
    pth, asp = sign_png('glass', 'GLASS TOWER', '#2f3438', '#e9ecec', SERIF, track=.2); st = next(s['xy'] for s in S['transit']['stations'] if s['name'] == '삼성'); c = g.centroid.coords[0]
    wall_strip(smb, g, (st[0] - c[0], st[1] - c[1]), b['h'] - 5.2, b['h'] - .9, mat_tex(pth, 'sg_glass'), aspect=asp, off=.45)
b, g = _bp('w840263996')   # 포스코센터 동관: 테헤란로 쪽
if b:
    pth, asp = sign_png('posco', 'posco', '#f6f5f0', '#3f6a6d', SANS, track=.06); wall_strip(smb, g, _toward_road(g, '테헤란로'), b['h'] - 6.0, b['h'] - 1.2, mat_tex(pth, 'sg_posco'), aspect=asp, off=.45)
b, g = _bp('w562011101')   # GS타워: 옥상 동쪽 끝의 흰 원통 + 청록 띠의 'GS'(세 번 되풀이해 어느 쪽에서도 읽힌다)
if b:
    _c, ax_, Lx_, _ly, _ = mrr_axes(g); e_ = ax_ if ax_[0] > 0 else -ax_; cc = np.array(_c) + e_ * Lx_ * .2; H_ = b['h']; R_ = 5.6
    smb.cyl((cc[0], cc[1], H_), R_, 8.5, mat_flat('#e6ecef'), mat_flat('#c9cdd0'), n=28)
    pth, asp = sign_png('gs', 'GS', '#f6f5f0', '#4f9070', SANSI, mx=1.25); wall_strip(smb, Point(*cc).buffer(R_, 16), (0, -1), H_ + 4.2, H_ + 8.3, mat_tex(pth, 'sg_gs'), w=2 * math.pi * (R_ + .3), off=.3, step=.6, reps=3.0)
b, g = _bp('w74013224')    # 현대백화점 무역센터점: 테헤란로 쪽 벽 동쪽 끝의 세로 전광판(벽에서 조금 띄워 건다) + 벽 위쪽 'HYUNDAI'
if b:
    dv = np.array(_toward_road(g, '테헤란로'), float); dv /= np.hypot(*dv); e_ = np.array([-dv[1], dv[0]]); e_ = e_ if e_[0] > 0 else -e_; c = np.array(g.centroid.coords[0]); _c, _ax, Lx_, Ly_, _ = mrr_axes(g)
    half = max(abs((np.array(q) - c) @ e_) for q in g.exterior.coords); H_ = b['h']; o1 = c + e_ * (half - 8.0)
    wall_strip(smb, g, dv, 7.0, H_ - 1.5, mat_tex(screen_png('hyundai', 96, 236, ['#b6573c', '#efbe3e', '#fdfdf3', '#c78169', '#984c2f', '#6ea8dd'], 11), 'sc_hyundai'), w=10.0, off=1.2, org=o1)
    wall_strip(smb, g, dv, 6.3, H_ - .8, mat_flat('#22272b'), w=11.0, off=.9, org=o1)
    pth, asp = sign_png('hyundai', 'HYUNDAI', '#67523e', '#dbc197', SANS, track=.3); wall_strip(smb, g, dv, H_ - 6.4, H_ - 2.4, mat_tex(pth, 'sg_hyundai'), aspect=asp, off=.4, org=c - e_ * half * .45)
b, g = _bp('w74056387')    # 코엑스 아티움: 삼성역 사거리 쪽 모퉁이를 감싼 전광판(지붕선 위로 솟는다. 높이 22 m 는 거리뷰 비례로 잡은 추정)
if b:
    st = next(s['xy'] for s in S['transit']['stations'] if s['name'] == '삼성'); c = g.centroid.coords[0]; dv = (st[0] - c[0], st[1] - c[1])
    wall_strip(smb, g, dv, 5.0, 22.0, mat_tex(screen_png('kpop', 512, 128, ['#6ea8dd', '#7cbefa', '#fdfdf3', '#567890', '#dde3e3', '#394f63'], 5), 'sc_kpop'), w=64.0, off=1.0)
    wall_strip(smb, g, dv, 4.3, 22.7, mat_flat('#22272b'), w=65.4, off=.7)
b, g = _bp('w74013220')    # 코엑스: 영동대로 쪽 유리벽
if b:
    pth, asp = sign_png('coex', 'coex', '#f6f5f0', '#3c5f96', SANS, track=.04); wall_strip(smb, g, _toward_road(g, '영동대로'), 17.5, 25.5, mat_tex(pth, 'sg_coex'), aspect=asp, off=.5)
if smb.f: toonify(smb.build('signs', 9780)); META[9780] = 'landmark:signs'; print('signs faces', len(smb.f), flush=True)
