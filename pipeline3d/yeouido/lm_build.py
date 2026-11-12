# 여의도 랜드마크 전용 빌더(사진 대조판, 2026-11-11). gen_area.py 가 건물 루프 직전에 exec 로 읽어 들인다(같은 전역: MB, mat_flat, mat_tex, skin, capf, …).
# 근거·출처·남은 차이는 LANDMARK-NOTES.md. 글자·로고는 넣지 않는다. ID·종류 이름(landmark:*)은 gen_area.py 의 것을 그대로 쓴다.

# ---------------- [5차] 픽셀아트 재질 ----------------
# 지붕 잠금·랜드마크 벽 잠금으로 cond 가 최종 그림에 그대로 들어가므로, 랜드마크의 벽은 양식 패스가 그린 이웃 타워와 결이 같아야 한다:
#  (1) 커튼월 = 평평한 면 색 + 또렷한 창 격자(창 칸 경계는 어두운 선, 12.5 cm/px 에서 약 1 px), 칸마다의 명도 잡음·그라데이션 없음, 층 띠는 한 색.
#  (2) 면 명암 3단계: 카메라 광선에서만 해 방향과 면의 기하 법선(True Normal)으로 밝은 면·중간·그늘 중 하나를 고른 평면 색(Emission) + 실제 조명 몫 TOON['k'](다른 건물의 그림자만 약하게 남긴다).
#      수평에 가까운 면(지붕, 법선 z > TOON['top'])은 원래 재질 그대로(4차 옥상·지붕 잠금 결과가 바뀌지 않게). 반사·하늘 그라데이션·스무스 음영은 카메라에 보이지 않는다.
#      다른 광선(그림자·반사광)에는 원래 재질이 쓰여 이웃 건물의 렌더는 그대로다. 윤곽·높이·ID 는 재질과 무관하다.
#  (3) 붉은 기둥·트러스: 평면 색 + 모서리에서 edge m 안의 1 px 어두운 테두리(Bevel 법선이 기하 법선에서 벗어나는 곳).
PXSP = {'parc': (.22, '#566b81')}   # 픽셀아트 판에서 층 띠를 바꾸는 텍스처(파크원: 짙은 띠가 너무 두드러져 좁고 유리에 가깝게)
TOON = dict(k=.40, t_mid=-.10, t_hi=.45, lv=(.62, .90, 1.28), top=.90, edge=.17, edge_dark=.35, line=.45, bayx=2.0, spf=.92)
PXGRID = os.environ.get('P3D_PXGRID', '1') == '1'     # 0 이면 4차까지의 격자·재질(전/후 비교용)
def _sunv():
    a, t = math.radians(50.0), math.radians(CAM.b['theta'] - 73.0)
    return (math.sin(a) * math.sin(t), -math.sin(a) * math.cos(t), math.cos(a))   # 해 쪽 단위 벡터(gen_area 의 sun 오일러 (50°, 0, θ−73°))
_tmat = {}
def toon_mat(m, edge=0.0, top=None, lv=None):
    top = TOON['top'] if top is None else top; lv = lv or TOON['lv']; key = (m.name, edge, top, lv)
    if key in _tmat: return _tmat[key]
    t = m.copy(); t.name = f"{m.name}~t{len(_tmat)}"; nt = t.node_tree; N = nt.nodes; L = nt.links
    pb = N['Principled BSDF']; out = N['Material Output']
    for n_ in N:
        if n_.bl_idname == 'ShaderNodeTexImage': n_.interpolation = 'Closest'
    bl = pb.inputs['Base Color'].links
    if bl: src = bl[0].from_socket
    else: rgb = N.new('ShaderNodeRGB'); rgb.outputs[0].default_value = pb.inputs['Base Color'].default_value; src = rgb.outputs[0]
    def mth(op, a, b=None, c=None):
        n_ = N.new('ShaderNodeMath'); n_.operation = op
        for i_, s_ in enumerate((a, b, c)):
            if s_ is None: continue
            if isinstance(s_, (int, float)): n_.inputs[i_].default_value = float(s_)
            else: L.new(s_, n_.inputs[i_])
        return n_.outputs[0]
    geo = N.new('ShaderNodeNewGeometry'); tn = geo.outputs['True Normal']
    dot = N.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'; L.new(tn, dot.inputs[0]); dot.inputs[1].default_value = _sunv(); ndl = dot.outputs['Value']
    lvl = mth('MULTIPLY_ADD', mth('GREATER_THAN', ndl, TOON['t_hi']), lv[2] - lv[1], mth('MULTIPLY_ADD', mth('GREATER_THAN', ndl, TOON['t_mid']), lv[1] - lv[0], lv[0]))
    if edge > 0:   # 테두리: 면의 UV 가 (가로 위치 m, 면 너비 m) 인 부재(ebox·ebeam)만. 가로 양 끝 edge m 를 어둡게
        uv = N.new('ShaderNodeUVMap'); uv.uv_map = 'uv'; su = N.new('ShaderNodeSeparateXYZ'); L.new(uv.outputs['UV'], su.inputs[0]); x_, w_ = su.outputs['X'], su.outputs['Y']
        e_ = mth('MAXIMUM', mth('LESS_THAN', x_, edge), mth('GREATER_THAN', x_, mth('SUBTRACT', w_, edge)))
        emul = mth('MULTIPLY_ADD', e_, TOON['edge_dark'] - 1.0, 1.0); lvl = mth('MULTIPLY', lvl, emul)
    else: emul = None
    sc_ = N.new('ShaderNodeVectorMath'); sc_.operation = 'SCALE'; L.new(src, sc_.inputs[0]); L.new(mth('MULTIPLY', lvl, 1.0 - TOON['k']), sc_.inputs['Scale'])
    em = N.new('ShaderNodeEmission'); L.new(sc_.outputs[0], em.inputs['Color']); em.inputs['Strength'].default_value = 1.0
    mk = N.new('ShaderNodeMixShader'); mk.inputs[0].default_value = TOON['k']; L.new(pb.outputs[0], mk.inputs[2])
    if emul is not None: L.new(mth('MULTIPLY', emul, TOON['k']), mk.inputs[0])   # 테두리는 실제 조명 몫도 같이 어둡게      # k × 실제 조명(1번 입력 비움 = 검정)
    ad = N.new('ShaderNodeAddShader'); L.new(em.outputs[0], ad.inputs[0]); L.new(mk.outputs[0], ad.inputs[1])
    sz = N.new('ShaderNodeSeparateXYZ'); L.new(tn, sz.inputs[0])
    mt = N.new('ShaderNodeMixShader'); L.new(mth('GREATER_THAN', sz.outputs['Z'], top), mt.inputs[0]); L.new(ad.outputs[0], mt.inputs[1]); L.new(pb.outputs[0], mt.inputs[2])
    lp = N.new('ShaderNodeLightPath'); mc = N.new('ShaderNodeMixShader'); L.new(lp.outputs['Is Camera Ray'], mc.inputs[0]); L.new(pb.outputs[0], mc.inputs[1]); L.new(mt.outputs[0], mc.inputs[2])
    L.new(mc.outputs[0], out.inputs['Surface']); _tmat[key] = t; return t
def toonify(o, edge=(), top=None, lv=None):
    """객체의 재질 칸을 툰 재질로 바꾼다. edge = 테두리를 넣을 재질 이름(mat_flat 의 hex) 모음."""
    if not PXGRID or o is None or o.type != 'MESH': return o
    for sl in o.material_slots:
        if sl.material is not None and '~t' not in sl.material.name: sl.material = toon_mat(sl.material, TOON['edge'] if sl.material.name.endswith('~frame') else 0.0, top, lv)
    return o
def mat_frame(hexs):
    """붉은 기둥·트러스용 재질(ebox·ebeam 전용 — UV 가 테두리 계산용이라 다른 면에 쓰면 안 된다). toonify 가 1 px 어두운 테두리를 넣는다."""
    k = hexs + '~frame'
    if k in _mat: return _mat[k]
    m = mat_flat(hexs).copy(); m.name = k; _mat[k] = m; return m
def ebox(mb, c, sx, sy, sz, m, ang=0.0, top=None):
    """MB.box 와 같은 상자, 옆면 UV = (가로 위치 m, 면 너비 m)."""
    ca, sa = math.cos(ang), math.sin(ang)
    q = [(c[0] + ca * dx - sa * dy, c[1] + sa * dx + ca * dy) for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy))]
    for k in range(4):
        a, b = q[k], q[(k + 1) % 4]; W_ = math.hypot(b[0] - a[0], b[1] - a[1])
        mb.face([(a[0], a[1], c[2]), (b[0], b[1], c[2]), (b[0], b[1], c[2] + sz), (a[0], a[1], c[2] + sz)], m, [(0, W_), (W_, W_), (W_, W_), (0, W_)])
    mb.face([(x, y, c[2] + sz) for x, y in q], top or m)
def eobox(mb, c, ax, sx, sy, z0, z1, m, top=None): ebox(mb, (c[0], c[1], z0), sx, sy, z1 - z0, m, math.atan2(ax[1], ax[0]), top)
def ebeam(mb, p0, p1, w, m, hgt=None):
    """gen_area.beam 과 같은 각기둥, 옆면 UV = (단면 가로 위치 m, 단면 너비 m) — 부재 길이 방향의 두 모서리에 테두리."""
    p0, p1 = np.array(p0, float), np.array(p1, float); d = p1 - p0; L_ = np.linalg.norm(d)
    if L_ < 1e-4: return
    d /= L_; up = np.array([0, 0, 1.0]) if abs(d[2]) < .95 else np.array([1.0, 0, 0])
    a = np.cross(d, up); a /= np.linalg.norm(a); b = np.cross(a, d); hw, hh = w / 2, (hgt or w) / 2
    q = [a * hw + b * hh, -a * hw + b * hh, -a * hw - b * hh, a * hw - b * hh]
    for k in range(4):
        u0, u1 = q[k], q[(k + 1) % 4]; W_ = float(np.linalg.norm(u1 - u0)); mb.face([tuple(p0 + u0), tuple(p0 + u1), tuple(p1 + u1), tuple(p1 + u0)], m, [(0, W_), (W_, W_), (W_, W_), (0, W_)])
    mb.face([tuple(p1 + u) for u in q[::-1]], m); mb.face([tuple(p0 + u) for u in q], m)

def grid_tex(key, glass, line, bay=1.5, flh=3.9, lw=.14, sp=0.0, spc=None, var=.035, nb=8, nf=8, grad=0.0):
    """고운 격자 유리(커튼월). [5차 PXGRID] 픽셀아트 판: 칸마다의 명도 잡음 없음, 창 칸 경계는 유리보다 어두운 선(가로 0.27 m ≈ 1.8 px, 세로 0.26 m ≈ 1.5 px @12.5 cm — 1 px 선은 굽기의 12색 포스터라이즈·외톨이 화소 정리에서 점선으로 끊긴다),
    스팬드럴(층 띠)은 한 색. 선 색이 유리보다 밝게 주어진 곳(은색 멀리언)은 유리를 어둡게 한 색으로 바꾼다."""
    if PXGRID:
        lum = lambda hx: sum(c * w for c, w in zip(ImageColor.getrgb(hx), (.299, .587, .114)))
        if lum(line) > lum(glass) * TOON['line']: line = shade(glass, TOON['line'])
        var, lw, lwv = 0.0, .27, .26; key = 'px_' + key; nb = max(2, int(round(nb / TOON['bayx']))); bay *= TOON['bayx']   # 창 칸을 두 배로(양식 패스의 큰 창 결), 되풀이 길이는 그대로
        if key[3:] in PXSP: sp, spc = PXSP[key[3:]]                                                                                   # 층 띠: 한 색(색을 준 곳은 그 색 — LG 베이지 판, FKI 청색 띠)
        elif sp and spc is None: spc = shade(glass, TOON['spf'])
    else: lwv = lw
    p = f'{TEXD}/grid_{key}.png'
    if os.path.exists(p): return p, nb * bay, nf * flh
    tw, th = int(nb * bay * RPPM), int(nf * flh * RPPM); im = Image.new('RGB', (tw, th), glass); d = ImageDraw.Draw(im); rnd = random.Random(zlib.crc32(key.encode()))
    bp, fp = bay * RPPM, flh * RPPM; w = max(1, int(round(lw * RPPM))); wv = max(1, int(round(lwv * RPPM)))
    for f in range(nf):
        for b_ in range(nb):
            x0_, y0_ = int(b_ * bp), int(f * fp); g = shade(glass, 1 + rnd.uniform(-var, var)) if var else glass
            d.rectangle([x0_, y0_, x0_ + int(bp), y0_ + int(fp)], fill=g)
            if sp: d.rectangle([x0_, y0_ + int(fp * (1 - sp)), x0_ + int(bp), y0_ + int(fp)], fill=spc or shade(glass, .86))
    if PXGRID:   # 선은 칸 경계에 걸치지 않고 칸 안쪽 아래·왼쪽에 둔다(되풀이 이음매에서 두 겹이 되지 않게)
        for f in range(nf): y_ = int((f + 1) * fp) - w; d.rectangle([0, y_, tw, y_ + w - 1], fill=line)
        for b_ in range(nb): x_ = int(b_ * bp); d.rectangle([x_, 0, x_ + wv - 1, th], fill=line)
    else:
        for f in range(nf + 1): d.line([(0, int(f * fp)), (tw, int(f * fp))], fill=line, width=w)
        for b_ in range(nb + 1): d.line([(int(b_ * bp), 0), (int(b_ * bp), th)], fill=line, width=w)
    im.save(p); return p, nb * bay, nf * flh

# ---------------- 63빌딩 ----------------
G63 = ('#d3a763', '#a67d45')   # 장밋빛 금색 반사 유리 / 멀리언(사진: 햇빛 면 #c9a27a 안팎, 그늘 면 #a8825c)
def b63(lm, idx):
    """63빌딩(사진 9장 대조). 긴 축 38°(북동–남서) 60 m. 넓은 두 면(북서·남동)이 아래로 갈수록 바깥으로 휘어 퍼지고(바닥 43.5 m → 위 26.7 m,
    OSM 파트: 120 m 까지의 날개 8.4 m), 좁은 끝면(북동 = 강 쪽, 남서)은 평면이라 그 윤곽이 A 자로 보인다. 끝면 가운데에 전망 승강기 통로가 2.2 m 튀어나와
    꼭대기까지 오르고(청회색 유리, 양옆 짙은 세로줄), 끝면에는 짙은 가로 두 줄 띠가 두 곳(약 32 %, 60 %), 모든 면 꼭대기 아래(약 93 %)에 짙은 띠가 돈다.
    지붕: 밝은 테두리, 낮은 기계실, 강 쪽 끝에서 1/4 지점에 붉고 흰 안테나(약 22 m)."""
    poly = unary_union([P(r) for r in lm['rings']]); c, ax_, Lx, Ly, _ = mrr_axes(poly)
    if ax_[0] + ax_[1] < 0: ax_ = -ax_          # +u = 북동(강 쪽 끝)
    nv = np.array([-ax_[1], ax_[0]]); H = 249.0; SD, SW = 2.2, 3.25; hu = Lx / 2 - SD; hv0, hvt, ZF = Ly / 2, 13.35, 150.0; mb = MB()
    path, tw, th = grid_tex('gold63', G63[0], G63[1], 1.5, 3.9); gm = mat_tex(path, 'gold63')
    sp_, stw, sth = grid_tex('shaft63', '#74889a', '#4f5d6a', 1.6, 3.9, var=.05); sm = mat_tex(sp_, 'shaft63')
    dk = mat_flat('#4a3f33'); dk2 = mat_flat('#5a4c3a')
    def prof(z): t = min(1.0, z / ZF); return hvt + (hv0 - hvt) * (1 - t) ** 1.7
    def ring(z):
        hv = prof(z); e = SW + .7
        return [(hu, -hv), (hu, -e), (hu, -SW), (hu + SD, -SW), (hu + SD, SW), (hu, SW), (hu, e), (hu, hv),
                (-hu, hv), (-hu, e), (-hu, SW), (-hu - SD, SW), (-hu - SD, -SW), (-hu, -SW), (-hu, -e), (-hu, -hv)]
    TAG = ['eg', 'dk', 'ss', 'sf', 'ss', 'dk', 'eg', 'wg', 'eg', 'dk', 'ss', 'sf', 'ss', 'dk', 'eg', 'wg']
    EB = [(77.0, 78.6), (80.6, 82.2), (147.0, 148.6), (150.6, 152.2)]; TB = (229.5, 233.0)   # 끝면 가로 두 줄 띠, 꼭대기 아래 띠
    zs = sorted(set([round(z, 3) for z in np.arange(0, H, 3.9)] + [a for b_ in EB for a in b_] + list(TB) + [H]))
    R_ = [[(u, v, z) for u, v in ring(z)] for z in zs]; n = 16
    W3 = lambda p: (c[0] + ax_[0] * p[0] + nv[0] * p[1], c[1] + ax_[1] * p[0] + nv[1] * p[1], p[2])
    for k in range(len(zs) - 1):
        zm = (zs[k] + zs[k + 1]) / 2; inE = any(a <= zm <= b_ for a, b_ in EB); inT = TB[0] <= zm <= TB[1]
        for i in range(n):
            a, b_, c2, d2 = R_[k][i], R_[k][(i + 1) % n], R_[k + 1][(i + 1) % n], R_[k + 1][i]; t = TAG[i]
            if t == 'sf': m, uvw_, uvh_ = sm, stw, sth
            elif t in ('ss', 'dk'): m, uvw_, uvh_ = dk, 1, 1
            elif inT or (t == 'eg' and inE): m, uvw_, uvh_ = dk2, 1, 1
            else: m, uvw_, uvh_ = gm, tw, th
            hc = (lambda p: p[0]) if t in ('wg', 'ss') else (lambda p: p[1])
            mb.face([W3(a), W3(b_), W3(c2), W3(d2)], m, [(hc(a) / uvw_, a[2] / uvh_), (hc(b_) / uvw_, b_[2] / uvh_), (hc(c2) / uvw_, c2[2] / uvh_), (hc(d2) / uvw_, d2[2] / uvh_)])
    top = Polygon([W3(p)[:2] for p in R_[-1]]).buffer(0); capf(mb, top, lambda x, y: H, mat_flat('#c2c5c7'))   # [2차 위성뷰] 옥상 바닥은 밝은 회백색
    cr_ = top.buffer(-0.7, join_style=2)
    for ring_, fl in ((top.exterior, False), (cr_.exterior, True)):  # 밝은 테두리(파라펫)
        cc = list(ring_.coords)
        for a_, q in zip(cc[:-1], cc[1:]):
            pts = [(a_[0], a_[1], H), (q[0], q[1], H), (q[0], q[1], H + 1.3), (a_[0], a_[1], H + 1.3)]; mb.face(pts[::-1] if fl else pts, mat_flat('#d6cdb8'))
    for t in shapely.constrained_delaunay_triangles(top.difference(cr_)).geoms: mb.face([(x, y, H + 1.3) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat('#e0d8c4'))
    ang = math.atan2(ax_[1], ax_[0])
    # [2차 위성뷰] 옥상: 큰 기계실 상자는 없다. 가운데에서 남서쪽으로 살짝 치우친 낮은 단 위에 흰 고리 두 겹의 원형 헬리패드, 남동쪽 가장자리(강 쪽 절반)에 냉각탑 팬이 줄지어 있다.
    # [4차 지붕 잠금] 흰 바닥에 흰 고리라 안 보였다 → 단 윗면을 짙은 청회색으로, 고리 폭을 1 m 로(12.5 cm/px 에서 4 px 이상). 단의 크기·높이는 그대로.
    pc = c - ax_ * 7.0; mb.box((pc[0], pc[1], H), 15.0, 10.0, .7, mat_flat('#8f9498'), ang, mat_flat('#59626b'))
    for r0, r1 in ((5.2, 6.3), (8.0, 9.1)): _annulus(mb, pc, H + .76, r0, r1, mat_flat('#f6f6f2'))
    _frame(mb, pc, ax_, 14.6, 9.7, H + .72, .8, mat_flat('#e9c93f'))   # 단 가장자리 노란 선
    _curb(mb, top, H, .7, 1.7, .5, '#a3a6a8', '#8b9094')                 # 파라펫 안쪽 턱(파라펫 1.3 m 보다 낮아 윤곽은 그대로)
    for s_ in (5.0, 11.0, 17.0, 23.0): q_ = c + ax_ * s_ - nv * 9.6; mb.box((q_[0], q_[1], H), 2.0, 1.6, 1.8, mat_flat('#d9d8d2'), ang, mat_flat('#ecebe6')); mb.cyl((q_[0], q_[1], H + 1.8), 1.25, .06, mat_flat('#454b51'), n=12)
    q_ = c - ax_ * 25.0 + nv * 6.0; mb.box((q_[0], q_[1], H), 2.6, 2.2, 2.4, mat_flat('#b9b5aa'), ang, mat_flat('#8f8c84'))
    ac = c + ax_ * (hu * .5); mb.box((ac[0], ac[1], H), 3.2, 3.2, 5.0, mat_flat('#a29e94'), ang, mat_flat('#8a877f'))    # 안테나 받침
    for k in range(6): mb.cyl((ac[0], ac[1], H + 5.0 + k * 3.0), .7 - k * .09, 3.0, mat_flat('#c8402e' if k % 2 == 0 else '#efefea'), n=8)
    mb.cyl((ac[0], ac[1], H + 23.0), .12, 4.0, mat_flat('#d8d8d4'), n=6)
    toonify(mb.build('b63', idx))

def b63_podium(b, idx):
    """63빌딩 저층부(OSM 파트 15 m). 색 태그가 금·갈색이면 본체와 같은 금색 격자 유리, 흰색 계열(별관)은 흰 가로 띠 + 청회색 유리(사진: 본체 옆 낮은 유리 건물)."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 8: return
    h = max(b['h'], 12.0); mb = MB(); col = (b.get('colour') or '').lower()
    if col in ('gold', 'brown', ''):
        path, tw, th = grid_tex('gold63', G63[0], G63[1], 1.5, 3.9); skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'gold63'), tw, th); flat_roof(mb, poly, h, '#c9b890', '#a8a59c')
    else:
        path, tw, th = grid_tex('pod63', '#7e96a8', '#56687a', 1.6, 3.75, sp=.34, spc='#ece8de'); skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'pod63'), tw, th); flat_roof(mb, poly, h, '#ece8de', '#b4b2aa')
        if poly.area > 600: roof_kit(mb, poly, h, random.Random(b['seed']), 4)
    toonify(mb.build('b%d' % idx, idx))

# ---------------- 공통: 격자 유리 타워 ----------------
def _parapet(mb, poly, h, col, par=1.3):
    inner = poly.buffer(-0.5, join_style=2)
    if inner.geom_type != 'Polygon' or inner.area < 10: return
    for ring, fl in ((poly.exterior, False), (inner.exterior, True)):
        cc = list(ring.coords)
        for a_, q in zip(cc[:-1], cc[1:]):
            pts = [(a_[0], a_[1], h), (q[0], q[1], h), (q[0], q[1], h + par), (a_[0], a_[1], h + par)]; mb.face(pts[::-1] if fl else pts, mat_flat(col))
    for t in shapely.constrained_delaunay_triangles(poly.difference(inner)).geoms: mb.face([(x, y, h + par) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat(shade(col, 1.12)))
def _lobby(mb, poly, LB, glass, span, line):
    lp, ltw, lth = grid_tex(f'lob_{glass}_{LB}', shade(glass, .55), line, 3.0, LB, lw=.2, nf=1); skin(mb, poly, 0.0, lambda x, y: LB, mat_tex(lp, 'g' + lp), ltw, lth)
    cn = orient(poly.buffer(1.4, join_style=2), 1.0); skin(mb, cn, LB, lambda x, y: LB + .7, mat_flat(span), 1, 1); capf(mb, cn, lambda x, y: LB + .7, mat_flat(shade(span, .92)))
def gtower(b, idx, cfg):
    """격자 유리(또는 띠창) 평지붕 타워. cfg: glass, line, flh, bay, sp(스팬드럴 비율), spc(스팬드럴 색), hroof, lobby, crownband, kit."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = cfg.get('hroof') or b['h']; mb = MB(); LB = cfg.get('lobby', 8.0)
    key = f"{cfg['glass']}_{cfg.get('spc')}_{cfg.get('sp', 0)}_{cfg.get('flh', 4.0)}_{cfg.get('bay', 1.5)}"
    path, tw, th = grid_tex(key, cfg['glass'], cfg['line'], cfg.get('bay', 1.5), cfg.get('flh', 4.0), sp=cfg.get('sp', 0.0), spc=cfg.get('spc'), var=cfg.get('var', .04)); gm = mat_tex(path, 'g' + key)
    if LB: _lobby(mb, poly, LB, cfg['glass'], cfg.get('spc') or shade(cfg['glass'], .8), cfg['line'])
    skin(mb, poly, LB, lambda x, y: h, gm, tw, th); capf(mb, poly, lambda x, y: h, mat_flat('#9a9c9e')); pc = cfg.get('spc') or shade(cfg['glass'], .8); _parapet(mb, poly, h, pc)
    if cfg.get('crownband'): cb = orient(poly.buffer(.3, join_style=2), 1.0); skin(mb, cb, h - cfg['crownband'], lambda x, y: h + 1.3, mat_flat(pc), 1, 1)
    if cfg.get('heli') == 'tri' and poly.area > 900:   # [2차 위성뷰] LG트윈타워: 두 동 모두 옥상의 3/4 을 녹색 헬리패드(흰 테두리, 흰 세모 표지)가 덮고 남동쪽 가장자리에 회색 설비 띠
        c_, ax_, Lx, Ly, mc = mrr_axes(poly); rc = np.array(mc).mean(axis=0); se = ax_ if abs(ax_[0] * .62 - ax_[1] * .78) > .7 else np.array([-ax_[1], ax_[0]])
        if se[0] - se[1] < 0: se = -se
        Ls = Lx if se is ax_ else Ly; Lp = Ly if se is ax_ else Lx
        helipad(mb, rc - se * (.09 * Ls), se, h + .1, min(.37 * Ls, .42 * Lp), '#43996d', '#f1f1ec', 'tri', .5)
        q = rc + se * (.39 * Ls); obox(mb, q, se, .06 * Ls, .40 * Lp, h, h + 2.4, mat_flat('#96989a'), mat_flat('#84878a'))
        for t_ in (-.28, -.09, .09, .28): q2 = q + np.array([-se[1], se[0]]) * (t_ * Lp); obox(mb, q2, se, .045 * Ls, .06 * Lp, h + 2.4, h + 3.3, mat_flat('#c9cbc8'), mat_flat('#e4e5e0')); mb.cyl((q2[0], q2[1], h + 3.3), min(.045 * Ls, .06 * Lp) * .78, .06, mat_flat('#454b51'), n=12)   # [4차] 팬 원판
    elif cfg.get('roofk') == 'solar':   # [2차 위성뷰] FKI타워: 옥상 전체를 은백색 태양광 판이 줄지어 덮고(짧은 축 방향 줄무늬), 가운데에 네모난 작은 개구부
        c_, ax_, Lx, Ly, mc = mrr_axes(poly); rc = np.array(mc).mean(axis=0); nv_ = np.array([-ax_[1], ax_[0]]); N_ = 11; inn = poly.buffer(-1.6)
        for k in range(N_):
            u = (-.5 + (k + .5) / N_) * (Lx - 4)
            for v0, v1 in ((-.5, -.12), (.12, .5)) if abs(u) < .13 * Lx else ((-.5, .5),):
                q = Polygon([tuple(rc + ax_ * (u + du) + nv_ * (v * (Ly - 4))) for du, v in ((-1.9, v0), (1.9, v0), (1.9, v1), (-1.9, v1))]).intersection(inn)
                for g in parts(q):
                    if g.area > 2: g = orient(g, 1.0); skin(mb, g, h, lambda x, y: h + 1.5, mat_flat('#8d969c'), 1, 1); capf(mb, g, lambda x, y: h + 1.5, mat_flat('#dde2e5'))
        obox(mb, rc, ax_, .10 * Lx, .09 * Ly, h, h + 2.6, mat_flat('#eef0f0'), mat_flat('#7c848a'))
    else:
        core = poly.buffer(-max(3.0, 0.26 * mrr_axes(poly)[3]), join_style=2)
        if core.geom_type == 'Polygon' and core.area > 15: skin(mb, core, h, lambda x, y: h + 4.5, mat_flat('#a9aaa8'), 1, 1); capf(mb, core, lambda x, y: h + 4.5, mat_flat('#8c8e90'))
        roof_kit(mb, poly, h, random.Random(b['seed']), cfg.get('kit', 3))
    toonify(mb.build('b%d' % idx, idx))
def lg_low(b, idx):
    """[2차 위성뷰] LG트윈타워 두 동 사이 저층부(아트리움): 위에서 보면 짙은 유리 지붕에 격자 살이 촘촘하다. OSM 파트(4–20 m 계단)를 짙은 유리 + 격자 지붕으로."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 6: return
    h = max(b['h'], 4.0); mb = MB(); path, tw, th = grid_tex('lglow', '#3e4a55', '#7d8a94', 1.6, 4.0, var=.05)
    gm = mat_tex(path, 'glglow'); skin(mb, poly, 0.0, lambda x, y: h, gm, tw, th)
    for t in shapely.constrained_delaunay_triangles(poly).geoms:
        q = list(orient(t, 1.0).exterior.coords)[:-1]; mb.face([(x, y, h) for x, y in q], gm, [((x * .79 + y * .62) / tw, (-x * .62 + y * .79) / th) for x, y in q])
    toonify(mb.build('b%d' % idx, idx))

# ---------------- 옥상 공통(2차: 위성·항공뷰 대조) ----------------
def _curb(mb, poly, h, in0, in1, hz, face, topc):
    """[4차] 파라펫 안쪽으로 들인 낮은 턱: 윤곽에서 in0..in1 m 안쪽 띠를 hz 만큼 올린다(안쪽 수직면 + 윗면). 파라펫보다 낮게 써서 건물 윤곽은 바뀌지 않는다."""
    a, b_ = poly.buffer(-in0, join_style=2), poly.buffer(-in1, join_style=2)
    if a.is_empty or b_.is_empty or b_.geom_type != 'Polygon' or a.geom_type != 'Polygon' or b_.area < 12: return
    skin(mb, orient(b_, -1.0), h, lambda x, y: h + hz, mat_flat(face), 1, 1)
    for t in shapely.constrained_delaunay_triangles(a.difference(b_)).geoms: mb.face([(x, y, h + hz) for x, y in list(orient(t, 1.0).exterior.coords)[:-1]], mat_flat(topc))
def _cooler(mb, q, ax, z, s=.95, hz=1.25):
    """[4차] 냉각탑 한 대: 밝은 상자 + 짙은 팬 원판(지름 1.4 m — 12.5 cm/px 에서 약 11 px)."""
    obox(mb, q, ax, s, s, z, z + hz, mat_flat('#b9bcb8'), mat_flat('#e4e5e0')); mb.cyl((q[0], q[1], z + hz), s * .74, .06, mat_flat('#454b51'), n=12)
DECKV = ['#8f9296', '#7b8186', '#a39f95', '#4d9a72', '#5a9c86', '#8c8175', '#6c7c8a', '#9ba1a5', '#8f9296', '#58a17d']
def roof_std(mb, poly, h, up, hup, heli, seed):
    """[4차 지붕 잠금] 일반 타워 옥상(절차적, 시드마다 다름). 옥상이 양식 패스 없이 렌더 그대로 최종 그림에 들어가므로 평평한 단색 + 또렷한 색 구획 + 0.5 m 이상의 단순한 설비로 만든다.
    poly = 건물 윤곽, h = 옥상 바닥, up/hup = 그 위에 이미 서 있는 상자(기계실 또는 한 단 들어간 꼭대기)와 그 윗면 높이, heli = 그 위에 헬리패드가 있는가.
    윤곽 보존: 바닥 위 설비는 파라펫(1.4 m)보다 낮게, 상자 위 설비는 가장자리에서 2.6 m 이상 들여 1.5 m 이하로(35° 카메라에서 상자 윗변 밖으로 나오지 않는다)."""
    r = random.Random(seed * 7919 + 13); deck = r.choice(DECKV); inn = poly.buffer(-.5, join_style=2)
    for q in parts(inn):
        if q.area > 10: capf(mb, orient(q, 1.0), lambda x, y: h + .05, mat_flat(deck))
    _curb(mb, poly, h, .5, 1.4, .6, '#a9a79f', '#d0cec6')
    c_, ax_, Lx, Ly, mc = mrr_axes(poly); nv_ = np.array([-ax_[1], ax_[0]]); rc = np.array(mc).mean(axis=0)
    upok = up is not None and (not up.is_empty) and up.geom_type == 'Polygon' and up.area > 15
    if upok:
        topc = r.choice(['#b9b7ae', '#6b7278', '#a8a59c', '#c9c7bf']); ui = up.buffer(-.7, join_style=2)
        for q in parts(ui):
            if q.area > 8: capf(mb, orient(q, 1.0), lambda x, y: hup + .05, mat_flat(topc))
        e = up.buffer(-2.6, join_style=2)
        if not heli and e.geom_type == 'Polygon' and e.area > 14:
            ec, ea, eLx, eLy, emc = mrr_axes(e); en = np.array([-ea[1], ea[0]]); er = np.array(emc).mean(axis=0); safe = up.buffer(-2.55, join_style=2); sg = r.choice((-1, 1))
            wh = r.random() < .5
            for f_ in (1.0, .8, .62, .45):
                bx, by = min(3.6, eLx * .24) * f_, min(2.6, eLy * .42) * f_; q = er + ea * sg * (eLx / 2 - bx - .1) * f_
                if bx < .9 or not safe.contains(Polygon([tuple(q + ea * su * bx + en * sv * by) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))])): continue
                obox(mb, q, ea, bx, by, hup, hup + 1.5, mat_flat('#d9d9d3' if wh else '#7a8087'), mat_flat('#efefea' if wh else '#5d646b'))                      # 기계실 상자
                obox(mb, q, ea, bx * .45, by * .5, hup + 1.5, hup + 1.56, mat_flat('#59626b' if wh else '#c9cbc8')); break                                       # 윗면의 환기구 판
            n = int(min(4, max(0, (eLy - .2) // 2.5)))
            for k in range(n):
                q = er - ea * sg * (eLx / 2 - 1.1) * .9 + en * ((k - (n - 1) / 2) * 2.5) * .9
                if safe.contains(Point(*q).buffer(.9)): _cooler(mb, q, ea, hup, .85)
            if eLx > 16 and r.random() < .6:
                q = er - ea * sg * (eLx * .08)
                if safe.contains(Point(*q).buffer(1.6)): mb.cyl((q[0], q[1], hup), 1.5, 1.4, mat_flat('#d8d8d2'), mat_flat('#f0f0ea'), n=12)                   # 물탱크
    # 바닥 위(파라펫보다 낮은 것만): 긴 축 한쪽 끝에 냉각탑 줄, 반대쪽에 낮은 설비 상자
    free = inn.buffer(-1.9, join_style=2)
    if upok: free = free.difference(up.buffer(1.4))
    if not free.is_empty:
        sg = r.choice((-1, 1)); placed = 0
        for axis, L_, W_, oth in ((ax_, Lx, Ly, nv_), (nv_, Ly, Lx, ax_)):
            if placed: break
            uq = (np.array(mrr_axes(up)[4]).mean(axis=0) if upok else rc); ext = (max(abs((np.array(p) - uq) @ axis) for p in up.exterior.coords) if upok else 0.0)
            gap = L_ / 2 - ext
            if gap < 5.4: continue
            for s_ in (sg, -sg):
                u = (ext + L_ / 2) / 2 if upok else L_ / 2 - 3.6; n = int(min(5, (W_ - 6) // 2.5))
                if s_ == sg:
                    for k in range(n):
                        q = rc + axis * s_ * u + oth * ((k - (n - 1) / 2) * 2.5)
                        if free.contains(Point(*q).buffer(1.0)): _cooler(mb, q, axis, h + .05, .95, 1.2); placed += 1
                else:
                    q = rc + axis * s_ * u; bx, by = min(2.2, gap / 2 - 1.6), min(4.5, W_ * .22)
                    if bx > .7 and free.contains(Polygon([tuple(q + axis * a_ * bx + oth * b2 * by) for a_, b2 in ((-1, -1), (1, -1), (1, 1), (-1, 1))])):
                        obox(mb, q, axis, bx, by, h + .05, h + 1.3, mat_flat('#8a8f93'), mat_flat('#d9d9d3')); obox(mb, q, axis, bx * .5, by * .7, h + 1.3, h + 1.36, mat_flat('#59626b'))
def _annulus(mb, c, z, r0, r1, m, n=32, ax=None, k=1.0):
    """평평한 고리(타원 가능: ax 방향 반지름 r, 그 수직 방향 r·k)."""
    ax = np.array(ax if ax is not None else (1.0, 0.0), float); nv_ = np.array([-ax[1], ax[0]])
    P_ = lambda r, t: (c[0] + ax[0] * r * math.cos(t) + nv_[0] * r * k * math.sin(t), c[1] + ax[1] * r * math.cos(t) + nv_[1] * r * k * math.sin(t), z)
    for i in range(n): t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n; mb.face([P_(r0, t0), P_(r1, t0), P_(r1, t1), P_(r0, t1)], m)
def _disc(mb, c, z, r, m, n=32, ax=None, k=1.0):
    ax = np.array(ax if ax is not None else (1.0, 0.0), float); nv_ = np.array([-ax[1], ax[0]])
    mb.face([(c[0] + ax[0] * r * math.cos(2 * math.pi * i / n) + nv_[0] * r * k * math.sin(2 * math.pi * i / n), c[1] + ax[1] * r * math.cos(2 * math.pi * i / n) + nv_[1] * r * k * math.sin(2 * math.pi * i / n), z) for i in range(n)], m)
def _frame(mb, c, ax, hx, hy, z, w, m):
    """바닥에 그린 사각 테두리 선(폭 w)."""
    ax = np.array(ax, float); nv_ = np.array([-ax[1], ax[0]]); c = np.array(c[:2], float)
    for su, sv, sx, sy in ((0, 1, hx, w / 2), (0, -1, hx, w / 2), (1, 0, w / 2, hy - w), (-1, 0, w / 2, hy - w)):   # [4차] 모서리에서 겹치지 않게(겹친 윗면이 검은 점으로 렌더됐다)
        q = c + ax * su * (hx - w / 2) + nv_ * sv * (hy - w / 2); obox(mb, q, ax, sx, sy, z, z + .06, m)
def helipad(mb, c, ax, z, half, pad='#8d949c', line='#f1f1ec', mark='circle', lift=.5, side=None):
    """옥상 헬리패드: 네모 판 + 흰 테두리 + 표지(원 고리 또는 세모). 글자(H)는 그리지 않는다."""
    obox(mb, c, ax, half, half, z, z + lift, mat_flat(side or shade(pad, .8)), mat_flat(pad)); zt = z + lift + .04; lm_ = mat_flat(line)
    _frame(mb, c, ax, half * .9, half * .9, zt, max(.8, half * .075), lm_)   # [4차] 선 폭 0.8–1 m 로 과장(12.5 cm/px 에서 4 px 이상)
    if mark == 'circle': w_ = max(.9, half * .09); _annulus(mb, c, zt, half * .5 - w_ / 2, half * .5 + w_ / 2, lm_)
    elif mark == 'tri':   # LG트윈타워: 녹색 바탕에 흰 세모 표지
        ax = np.array(ax, float); nv_ = np.array([-ax[1], ax[0]]); c2 = np.array(c[:2], float); r = half * .5
        t3 = [c2 + ax * r * math.cos(a_) + nv_ * r * math.sin(a_) for a_ in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6)]
        w_ = max(.9, half * .085); ti = [c2 + (p_ - c2) * (1 - 2 * w_ / r) for p_ in t3]   # [4차] 세모 테를 평평한 띠 3장으로(각기둥 끝이 겹쳐 모서리에 검은 점이 생겼다)
        for i in range(3): j = (i + 1) % 3; mb.face([(*t3[i], zt + .02), (*t3[j], zt + .02), (*ti[j], zt + .02), (*ti[i], zt + .02)], lm_)
HELIV = [('#4d9a72', '#f6f6f1'), ('#3f8a63', '#f6f6f1'), ('#626a72', '#f6f6f1'), ('#59626b', '#f0cc3a'), ('#3f8f7c', '#f6f6f1')]   # [4차] 회색 바탕은 흰 선과 대비가 나게 짙게   # 위성뷰: 여의도 고층 옥상은 녹색 방수 바닥에 흰 원이 가장 많고 회색 바탕도 섞여 있다
def heli_std(mb, c, ax, z, Ly, rnd):
    """일반 타워 옥상 헬리패드(절차적): 네모 판 + 테두리 + 원. 건물마다 실제 유무를 맞춘 것은 아니다."""
    pad, line = rnd.choice(HELIV); helipad(mb, c, ax, z, min(10.0, .34 * Ly), pad, line, 'circle', .5)

# ---------------- 파크원(타워 1·2) ----------------
def parc(b, idx, cfg):
    """파크원 타워. 벽면은 1차(옆모습 사진), 옥상은 2차(위성·항공뷰): 평면은 모서리가 접힌 사각형이고, 꼭대기 둘레를 밝은 베이지색 띠(폭 약 4 m)가 돈다.
    띠 안쪽은 한 단 낮은 회색 바닥이고 북서쪽 절반에 네모난 헬리패드(회색 판, 흰 네모 테두리 + 흰 원)가 올라앉아 있으며 남동쪽에 흰 설비 상자와 좁은 녹지 띠가 있다.
    붉은 기둥은 모서리마다 한 쌍씩 올라와 지붕 높이에서 안쪽으로 꺾여 접힌 모서리 양 끝에 닿고, 그 사이를 붉은 보가 잇는다(위에서 보면 네 모서리에 붉은 꺾쇠)."""
    full = orient(P(b['rings']), 1.0); h = cfg['hroof']; ht = cfg['htop']; mb = MB(); LB = 12.0
    path, tw, th = grid_tex('parc', '#5f7890', '#8fa3b3', 1.5, 4.4, sp=.3, spc='#4c6076', var=.05); gm = mat_tex(path, 'gparc')
    # [3차 위성뷰] 평면은 북서쪽의 거의 정사각형 본체(약 51×46 m)와 남동쪽으로 튀어나온 좁은 띠(약 34×12.5 m)로 나뉜다. 남동쪽 띠는 본체 밖에 붙은 승강기·계단 코어:
    # 밝은 회색 가로 줄무늬 외장의 수직 통 3개가 짙은 유리 띠를 사이에 두고 서 있고, 가운데 통은 지붕 가까이(약 0.92 h), 양옆 통은 더 낮다(약 0.70 h). 통 꼭대기는 밝은 베이지 평지붕.
    c0, a0, Lx0, Ly0, mc0 = mrr_axes(full); a0 = -a0 if a0[1] - a0[0] < 0 else a0; n0 = np.array([-a0[1], a0[0]]); r0 = np.array(mc0).mean(axis=0); CD = cfg.get('core_d', 12.5)
    cut = Polygon([tuple(r0 + a0 * u + n0 * v) for u, v in ((-Lx0 / 2 + CD, -Ly0), (Lx0, -Ly0), (Lx0, Ly0), (-Lx0 / 2 + CD, Ly0))])
    poly = orient(max(parts(full.intersection(cut)), key=lambda g: g.area), 1.0); czone = full.difference(cut.buffer(.01))
    cp_, ctw, cth = grid_tex('parccore', '#c3c6c2', '#9a9f9b', 3.0, 1.1, lw=.16, var=.02); cm = mat_tex(cp_, 'gparccore'); dkg = mat_flat('#2f3d4a')
    for g in parts(czone):
        if g.area < 30: continue
        gc, ga, gLx, gLy, gmc = mrr_axes(g); gr = np.array(gmc).mean(axis=0); wv = (gLx if abs(ga @ n0) > .7 else gLy); dv_ = (gLy if abs(ga @ n0) > .7 else gLx)   # wv = 가로(본체 면을 따라), dv_ = 튀어나온 깊이
        skin(mb, orient(g, 1.0), 0.0, lambda x, y: .66 * h, dkg, 1, 1); capf(mb, g, lambda x, y: .66 * h, mat_flat('#59636e'))                                    # 통 사이의 짙은 유리 띠(우묵한 바탕)
        for fv, fw, fh in ((-.345, .25, .70), (0.0, .30, .92), (.345, .25, .70)):
            q = orient(Polygon([tuple(gr + a0 * su * (dv_ / 2 + .5) + n0 * (fv * wv + sv * fw * wv / 2)) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]), 1.0); hz = fh * h
            skin(mb, q, 0.0, lambda x, y: hz, cm, ctw, cth); capf(mb, q, lambda x, y: hz, mat_flat('#c9c0ae')); _parapet(mb, q, hz, '#b3a995', 1.0)
            qc_ = np.array(q.centroid.coords[0])
            if fh > .9: obox(mb, qc_, a0, 2.6, 2.6, hz, hz + 2.2, mat_flat('#d7d7d2'), mat_flat('#e6e6e1')); [mb.cyl((qc_[0] + a0[0] * du + n0[0] * dw, qc_[1] + a0[1] * du + n0[1] * dw, hz + 2.2), .8, .1, mat_flat('#7a7f84'), n=10) for du in (-1.2, 1.2) for dw in (-1.2, 1.2)]
            else: obox(mb, qc_, a0, 1.6, 1.2, hz, hz + 1.6, mat_flat('#9a9b97'), mat_flat('#85878a'))
    _lobby(mb, poly, LB, '#5f7890', '#b5382a', '#8fa3b3'); skin(mb, poly, LB, lambda x, y: h, gm, tw, th); capf(mb, poly, lambda x, y: h, mat_flat('#8f9296'))
    for fr in cfg.get('belts', ()): zb_ = h * fr; bp_ = orient(poly.buffer(.25, join_style=2), 1.0); skin(mb, bp_, zb_, lambda x, y: zb_ + 4.4, mat_flat('#3f4f60'), 1, 1)
    fm = mat_frame(cfg['frame']); ax_, nv, Lx, Ly = a0, n0, Lx0 - CD, Ly0; rc = r0 + a0 * (CD / 2); ang0 = math.atan2(ax_[1], ax_[0])   # 본체 사각형(+u = 북서)
    K = lambda su, sv, ou=0.0, ov=0.0: rc + ax_ * su * (Lx / 2 + ou) + nv * sv * (Ly / 2 + ov)
    CH = 8.0; hc = ht - 1.2; zd = hc - 2.2            # 접힌 모서리 길이, 띠 윗면, 안쪽 바닥
    for su in (-1, 1):
        for sv in (-1, 1):
            for fr in cfg.get('belts', ()):   # [3차 위성뷰] 기계층 높이에서 붉은 기둥 밖으로 내민 회색 받침(아웃리거 끝)
                for pq, sx_, sy_ in ((K(su, sv, -4.9, 1.9), 3.4, 1.0), (K(su, sv, 1.9, -4.9), 1.0, 3.4)): mb.box((pq[0], pq[1], h * fr - .4), sx_, sy_, 5.2, mat_flat('#a9aaa6'), ang0, mat_flat('#bdbeba'))
            for o in (2.2, 7.6):   # 면마다 양 끝의 붉은 기둥(1차 그대로)
                p_ = K(su, sv, -o, .9); ebox(mb, (p_[0], p_[1], 0), .8, 1.0, h + 1.0, fm, ang0)
                p_ = K(su, sv, .9, -o); ebox(mb, (p_[0], p_[1], 0), 1.0, .8, h + 1.0, fm, ang0)
            A, B = K(su, sv, -CH - .6, -.6), K(su, sv, -.6, -CH - .6)     # 접힌 모서리의 양 끝(띠 높이)
            ebeam(mb, (*K(su, sv, -2.2, .9), h + .6), (*A, hc + .4), 1.5, fm); ebeam(mb, (*K(su, sv, .9, -2.2), h + .6), (*B, hc + .4), 1.5, fm)   # 기둥 머리가 안쪽으로 꺾임
            ebeam(mb, (*A, hc + .7), (*B, hc + .7), 1.6, fm)                                                                                       # 모서리의 붉은 보
    hb = lambda c_, d_, hl, z0_, z1_: ebeam(mb, (*(c_ - d_ * hl), (z0_ + z1_) / 2), (*(c_ + d_ * hl), (z0_ + z1_) / 2), 1.1, fm, z1_ - z0_)   # 가로 붉은 보(obox 와 같은 각기둥, 위·아래 모서리에 테두리)
    for sv in (-1, 1): hb(K(0, sv, 0, .55), ax_, Lx / 2, LB, LB + 1.4); hb(K(0, sv, 0, .55), ax_, Lx / 2 - 2.2, h - .6, h + 1.0)
    for su in (-1, 1): hb(K(su, 0, .55, 0), nv, Ly / 2, LB, LB + 1.4); hb(K(su, 0, .55, 0), nv, Ly / 2 - 2.2, h - .6, h + 1.0)
    def octa(off, ch):
        pts = []
        for su, sv in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            pa, pb = K(su, sv, off - ch, off), K(su, sv, off, off - ch); pts += [pb, pa] if su * sv > 0 else [pa, pb]
        return orient(Polygon([tuple(p) for p in pts]), 1.0)
    crown = octa(-1.0, CH); outer = octa(.4, CH + .6); inner = octa(-5.0, CH - 1.6)
    skin(mb, crown, h, lambda x, y: hc - 1.4, mat_flat('#55616d'), 1, 1)                                   # 꼭대기 층(짙은 루버 벽)
    skin(mb, outer, hc - 1.4, lambda x, y: hc, mat_flat('#b3a995'), 1, 1); capf(mb, outer.difference(crown.buffer(-.01)), lambda x, y: hc - 1.4, mat_flat('#8d8676'))
    capf(mb, outer.difference(inner), lambda x, y: hc, mat_flat('#c9c0ae'))                               # 둘레의 밝은 베이지 띠
    skin(mb, orient(inner, -1.0), zd, lambda x, y: hc, mat_flat('#9d9789'), 1, 1); capf(mb, inner, lambda x, y: zd, mat_flat('#7c8288'))
    hp = rc + ax_ * (.05 * Lx); half = min(12.0, .27 * Ly)
    obox(mb, hp, ax_, half + 1.5, half + 1.5, zd, zd + .25, mat_flat('#a3a8ab'))                          # 헬리패드 둘레 바닥
    helipad(mb, hp, ax_, zd + .25, half, '#5d666f', '#f6f6f1', 'circle', 1.3, '#7b8188')   # [4차] 판을 짙게(전에는 바닥과 같은 회색이라 흰 선이 묻혔다)
    g0 = rc - ax_ * (Lx / 2 - 8.0); obox(mb, g0, ax_, 1.7, .30 * Ly, zd, zd + .45, mat_flat('#5f7345'))   # 남동쪽 좁은 녹지 띠
    m0 = rc - ax_ * (.31 * Lx) + nv * (.30 * Ly); obox(mb, m0, ax_, 3.2, 2.6, zd, zd + 2.6, mat_flat('#d7d7d2'), mat_flat('#e6e6e1'))   # 흰 설비 상자
    for sv_, sx_, sy_, hz_ in ((-.22, 2.2, 4.0, 2.0), (.27, 1.6, 1.6, 1.6)): q_ = rc - ax_ * (.31 * Lx) + nv * ((sv_ - .3) * Ly); obox(mb, q_, ax_, sx_, sy_, zd, zd + hz_, mat_flat('#9a9b97'), mat_flat('#85878a'))
    toonify(mb.build('b%d' % idx, idx))

# ---------------- IFC·콘래드: 비스듬히 깎인 유리 결정 ----------------
def _halfplane(nx, ny, cc, R=5000.0):
    """nx·x + ny·y ≤ cc 인 반평면(큰 사각형)."""
    L = math.hypot(nx, ny); nx, ny, cc = nx / L, ny / L, cc / L; p0 = np.array([nx * cc, ny * cc]); t = np.array([-ny, nx]); n = np.array([nx, ny])
    return Polygon([tuple(p0 + t * R), tuple(p0 - t * R), tuple(p0 - t * R - n * 2 * R), tuple(p0 + t * R - n * 2 * R)])
def crystal(b, idx, cfg):
    """평면(OSM) 위로 올린 각기둥을 기운 평면 여러 장으로 깎는다: 지붕 경사면 1장 + 모서리에서 위로 갈수록 깊어지는 가파른 깎임면(facets).
    cfg: glass, line, flh, rise, sdir(지붕이 높아지는 방향), facets=[(방향 x,y, 시작 높이 비율, 꼭대기에서의 깊이 m)], top='disc'(3 IFC 헬리포트)."""
    poly = orient(P(b['rings']), 1.0)
    if poly.geom_type != 'Polygon' or poly.area < 20: return
    h = cfg.get('hroof') or b['h']; mb = MB(); LB = 9.0; c, ax_, Lx, Ly, mc = mrr_axes(poly); xy = np.array(poly.exterior.coords)
    key = f"cry_{cfg['glass']}"; path, tw, th = grid_tex(key, cfg['glass'], cfg['line'], 1.5, cfg.get('flh', 4.2), sp=.22, spc=shade(cfg['glass'], .86), var=.05); gm = mat_tex(path, 'g' + key)
    planes = []   # (a, b, c0): z = a·x + b·y + c0
    dv = np.array(cfg.get('sdir', (0, 1)), float); dv /= np.hypot(*dv); pr = xy @ dv; rise = cfg.get('rise', 0.0); sl = rise / max(pr.max() - pr.min(), 1e-6)
    planes.append((sl * dv[0], sl * dv[1], h - rise - sl * pr.min(), 'top'))
    for fx, fy, zf, d in cfg.get('facets', ()):
        n = np.array([fx, fy], float); n /= np.hypot(*n); smax = (xy @ n).max(); k = (h - zf * h) / d
        planes.append((-k * n[0], -k * n[1], zf * h + k * smax, 'facet'))
    _lobby(mb, poly, LB, cfg['glass'], shade(cfg['glass'], .8), cfg['line'])
    for i, (a, b_, c0, kind) in enumerate(planes):
        reg = poly
        for j, (a2, b2, c2, _) in enumerate(planes):
            if j != i: reg = reg.intersection(_halfplane(a - a2, b_ - b2, c2 - c0))
        zf_ = lambda x, y, a=a, b_=b_, c0=c0: a * x + b_ * y + c0
        for g in parts(reg):
            if g.area < .5: continue
            g = orient(g, 1.0)
            if kind == 'top':   # [2차 위성뷰] 기운 지붕면은 유리가 아니다: 밝은 회백색 테(틀) 안에 회색 바닥(1·콘래드: 냉각탑 팬이 놓인 우묵한 설비 바닥, 2: 밋밋한 회백색 판, 3: 타원 받침)
                rk = cfg.get('roofk', 'fans'); inn = g.buffer(-2.4, join_style=2)
                if inn.is_empty or inn.geom_type != 'Polygon' or inn.area < 40: capf(mb, g, zf_, mat_flat('#c9ced2'))
                else:
                    capf(mb, g.difference(inn), zf_, mat_flat('#d3d7da')); zin = (lambda x, y: zf_(x, y) - (0.0 if rk == 'plain' else 1.6))
                    capf(mb, inn, zin, mat_flat({'plain': '#c6c5be', 'fans': cfg.get('roofc', '#757b81'), 'oval': '#8a9096'}[rk]))
                    if rk != 'plain': [mb.face([(p0[0], p0[1], zin(*p0)), (p1[0], p1[1], zin(*p1)), (p1[0], p1[1], zf_(*p1)), (p0[0], p0[1], zf_(*p0))][::-1], mat_flat('#a4aaae')) for p0, p1 in zip(list(inn.exterior.coords)[:-1], list(inn.exterior.coords)[1:])]
                    if rk == 'fans':
                        ic = np.array(inn.centroid.coords[0]); core_ = inn.buffer(-3.5)
                        for iu in (-1.5, -.5, .5, 1.5):
                            for iv in (-.5, .5):
                                q = ic + ax_ * iu * 5.2 + np.array([-ax_[1], ax_[0]]) * iv * 5.6
                                if core_.contains(Point(*q)): z_ = zin(*q); obox(mb, q, ax_, 2.1, 2.1, z_, z_ + 1.5, mat_flat('#b4b8ba'), mat_flat('#c9cccd')); mb.cyl((q[0], q[1], z_ + 1.5), 1.5, .08, mat_flat('#5f6468'), n=12)
            else:
                t = np.array([-b_, a]); t /= np.hypot(*t)
                for tr in shapely.constrained_delaunay_triangles(g).geoms:
                    q = list(orient(tr, 1.0).exterior.coords)[:-1]; mb.face([(x, y, zf_(x, y)) for x, y in q], gm, [((x * t[0] + y * t[1]) / tw, zf_(x, y) / th) for x, y in q])
            cc = list(g.exterior.coords)
            for p0, p1 in zip(cc[:-1], cc[1:]):
                mid = Point((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2); L_ = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                if L_ < .05 or poly.exterior.distance(mid) > 1e-4: continue
                e = ((p1[0] - p0[0]) / L_, (p1[1] - p0[1]) / L_); u0, u1 = p0[0] * e[0] + p0[1] * e[1], p1[0] * e[0] + p1[1] * e[1]; z0_, z1_ = max(LB, zf_(*p0)), max(LB, zf_(*p1))
                mb.face([(p0[0], p0[1], LB), (p1[0], p1[1], LB), (p1[0], p1[1], z1_), (p0[0], p0[1], z0_)], gm, [(u0 / tw, LB / th), (u1 / tw, LB / th), (u1 / tw, z1_ / th), (u0 / tw, z0_ / th)])
    if cfg.get('top') == 'disc':   # 3 IFC [2차 위성뷰]: 지붕 가운데의 타원 받침(긴 축 = 건물 긴 축, 약 38×24 m) — 흰 고리 테, 회색 바닥에 짙은 판, 한쪽에 흰 원 헬리패드
        pc = c + dv * (0.04 * Ly); zt = planes[0][0] * pc[0] + planes[0][1] * pc[1] + planes[0][2]; ht_ = cfg.get('htop', h + 8); R = .30 * Lx; kk = .62; nv_ = np.array([-ax_[1], ax_[0]])
        E = lambda r, t, z: (pc[0] + ax_[0] * r * math.cos(t) + nv_[0] * r * kk * math.sin(t), pc[1] + ax_[1] * r * math.cos(t) + nv_[1] * r * kk * math.sin(t), z)
        for k in range(8): a0 = 2 * math.pi * k / 8; beam(mb, E(R * .6, a0, zt - 4), E(R * .9, a0 + .3, ht_ - 1.2), .5, mat_flat('#c9ced3'))
        for k in range(32): t0, t1 = 2 * math.pi * k / 32, 2 * math.pi * (k + 1) / 32; mb.face([E(R, t0, ht_ - 1.4), E(R, t1, ht_ - 1.4), E(R, t1, ht_), E(R, t0, ht_)], mat_flat('#d5d9dc'))
        _disc(mb, pc, ht_, R, mat_flat('#8d949a'), 32, ax_, kk)
        for z_ in (ht_ + .05, ht_ + 1.5): _annulus(mb, pc, z_, R * .97, R * 1.07, mat_flat('#f0f1f1'), 32, ax_, kk)
        for k in range(16): t0 = 2 * math.pi * k / 16; beam(mb, E(R * 1.02, t0, ht_), E(R * 1.02, t0, ht_ + 1.5), .3, mat_flat('#f0f1f1'))
        for su in (-.45, .12): obox(mb, pc + ax_ * (su * R + .16 * R), ax_, .22 * R, .36 * R * kk * 1.6, ht_, ht_ + .12, mat_flat('#4c5661'))   # 짙은 판(태양광으로 보임)
        hc_ = pc + ax_ * (.52 * R); _disc(mb, hc_, ht_ + .2, 5.6, mat_flat('#f6f6f1'), 24); _disc(mb, hc_, ht_ + .26, 4.6, mat_flat('#59626b'), 24); _annulus(mb, hc_, ht_ + .3, 2.0, 2.9, mat_flat('#f6f6f1'), 24)
    toonify(mb.build('cry%d' % idx, idx))   # 이름이 b<idx> 가 아니면 건물 루프의 부드러운 음영을 받지 않는다(깎임면 모서리가 또렷해야 함)

# ---------------- 더현대 서울 ----------------
def hyundai(b, idx):
    """더현대 서울(2차: 위성·항공뷰 대조; 1차는 추정이었다). 평면 약 166×99 m 사각형. 지붕은 격자로 나뉜다: 가운데 긴 축을 따라 정사각형 옥상 정원 3칸
    (짙은 풀색, X 자 길, 한가운데 작은 유리 천창), 그 둘레와 칸 사이를 청회색 유리 띠가 지나고, 양옆으로 회색 설비·루버 판(칸마다 가운데 흰 상자).
    붉은 마스트는 8개 — 긴 변 양쪽에 4개씩, 정원 칸의 경계선(긴 축의 ±0.115 L, ±0.345 L)에 마주 보고 선다. 위에서 보면 변에서 안쪽으로 폭의 0.4 배쯤
    뻗은 붉은 버들잎(렌즈) 모양 트러스다. 바깥 끝이 높이 솟고(높이는 추정 16 m) 안쪽 끝이 유리 띠에 닿는다."""
    poly = orient(P(b['rings']), 1.0); h = max(b['h'], 34.0); mb = MB()
    if PXGRID:   # [5차 사진(이미지 검색, 보기만)] 벽은 세로 핀이 아니라 흰·은색 가로 루버 띠가 겹겹이 두른 외장(긴 저층 상자) → 가로 띠 격자(재질만)
        path, tw, th = grid_tex('hyundai5', '#e4e3dd', '#8f969b', 6.0, 1.35, sp=.30, spc='#c9ccce'); skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'ghyundai5'), tw, th)
    else:
        path, tw, th = finwall_tex('hyundai2', '#eceae4', '#7f97a8', '#f6f5f0', bay=2.2, flh=5.4, finw=.7)
        skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'fin_' + path), tw, th)
    flat_roof(mb, poly, h, '#e9e7e1', '#8b9297')
    c_, ax_, Lx, Ly, mc = mrr_axes(poly); nv = np.array([-ax_[1], ax_[0]]); rc = np.array(mc).mean(axis=0); red = mat_frame('#c8452f'); inner = poly.buffer(-1.2)
    glass = mat_flat('#8ea4b0'); glt = mat_flat('#9db3be'); green = mat_flat('#586b3d'); pathc = mat_flat('#bdbcab'); pan = mat_flat('#7f868b'); pant = mat_flat('#949ba0'); wht = mat_flat('#e2e2dc')
    US = [-.345 * Lx, -.115 * Lx, .115 * Lx, .345 * Lx]; BW = 2.8; VG = .19 * Ly; VB = .235 * Ly; VP = .47 * Ly   # 마스트 선, 유리 띠 반폭, 정원 반폭, 긴 유리 띠 바깥, 판 바깥
    def ob(u0, u1, v0, v1, z0, z1, m, top=None):
        q = Polygon([tuple(rc + ax_ * u + nv * v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]).intersection(inner)
        for g in parts(q):
            if g.area > 1: g = orient(g, 1.0); skin(mb, g, z0, lambda x, y: z1, m, 1, 1); capf(mb, g, lambda x, y: z1, top or m)
    ob(US[0] - BW, US[-1] + BW, -VB, VB, h, h + 1.0, glass, glt)                                # 유리 띠(정원 둘레와 칸 사이)
    for u in US: ob(u - BW, u + BW, -VP, -VB, h, h + 1.0, glass, glt); ob(u - BW, u + BW, VB, VP, h, h + 1.0, glass, glt)                             # 마스트 선을 따라 지붕을 가로지르는 유리 띠
    for k in range(3):                                                                           # 옥상 정원 3칸
        u0, u1 = US[k] + BW, US[k + 1] - BW; uc = (u0 + u1) / 2; ob(u0, u1, -VG, VG, h + 1.0, h + 1.5, green)
        for sa, sb in ((1, 1), (1, -1)): beam(mb, (*(rc + ax_ * (uc - (u1 - u0) / 2 * sa) + nv * (-VG * sb)), h + 1.55), (*(rc + ax_ * (uc + (u1 - u0) / 2 * sa) + nv * (VG * sb)), h + 1.55), 1.0, pathc, .12)
        obox(mb, rc + ax_ * uc, ax_, 4.6, 4.6, h + 1.5, h + 2.6, glass, mat_flat('#a9c0cb'))     # 한가운데 유리 천창
    UB = [-Lx / 2 + 2] + US + [Lx / 2 - 2]
    for k in range(5):                                                                           # 양옆 설비·루버 판 + 흰 상자, 양 끝 칸은 가운데까지 판
        u0, u1 = UB[k] + (BW + 1.2 if k else 1.0), UB[k + 1] - (BW + 1.2 if k < 4 else 1.0)
        for sv in (-1, 1):
            v0, v1 = sorted((sv * (VB + 1.4), sv * VP)); ob(u0, u1, v0, v1, h, h + 1.3, pan, pant)
            q = rc + ax_ * ((u0 + u1) / 2) + nv * ((v0 + v1) / 2)
            if inner.contains(Point(*q)): obox(mb, q, ax_, 2.0, 2.0, h + 1.3, h + 2.9, wht)
            for t_ in (.25, .5, .75): beam(mb, (*(rc + ax_ * (u0 + (u1 - u0) * t_) + nv * v0), h + 1.36), (*(rc + ax_ * (u0 + (u1 - u0) * t_) + nv * v1), h + 1.36), .35, mat_flat('#6d7479'), .08)
        if k in (0, 4): ob(u0, u1, -VB + 1.4, VB - 1.4, h, h + 1.3, pan, pant)
    for u in US:                                                                                 # 붉은 마스트 8개(버들잎 모양 트러스)
        for sv in (-1, 1):
            O = np.array([*(rc + ax_ * u + nv * sv * (Ly / 2 + 2.5)), h + 16.0]); I = np.array([*(rc + ax_ * u + nv * sv * (.10 * Ly)), h + 1.6]); ch = []
            for sd in (-1, 1):
                pts = [O * (1 - t_) + I * t_ + np.array([*(ax_ * sd * 5.2 * math.sin(math.pi * t_)), 1.0 * math.sin(math.pi * t_)]) for t_ in np.linspace(0, 1, 9)]; ch.append(pts)
                for q0, q1 in zip(pts[:-1], pts[1:]): ebeam(mb, q0, q1, 1.5, red)
            for j in range(1, 8): ebeam(mb, ch[0][j], ch[1][j], .7, red)
            for j in range(1, 7): ebeam(mb, ch[0][j], ch[1][j + 1], .5, red)
            F = rc + ax_ * u + nv * sv * (Ly / 2 + 1.0)
            for sd in (-1, 1): ebeam(mb, (*(F + ax_ * sd * 2.6), 0.0), tuple(O), 1.3, red)          # 외벽을 따라 올라오는 붉은 다리
            for sd in (-1, 1): beam(mb, tuple(O), (*(rc + ax_ * (u + sd * .08 * Lx) + nv * sv * (.30 * Ly)), h + 1.4), .3, mat_flat('#b9b9b4'))   # 지붕을 매다는 케이블
    toonify(mb.build('b%d' % idx, idx))

# ---------------- FKI 회의장(타원 평면의 낮은 건물) ----------------
def fki_hall(b, idx):
    """전경련회관 컨퍼런스센터: 타원 평면, 은회색 금속·유리 외피의 낮은 건물(벽돌이 아님). 지붕은 완만한 볼록(추정)."""
    poly = orient(P(b['rings']), 1.0); h = max(b['h'], 14.0); mb = MB()
    path, tw, th = grid_tex('fkihall', '#aab6bd', '#7d8a92', 1.8, h / 3, sp=.3, spc='#c9d0d3'); skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'gfkihall'), tw, th)
    c = np.array(poly.centroid.coords[0]); prev = [(x, y, h) for x, y in list(poly.exterior.coords)[:-1]]; rm = mat_flat('#c3c9cc')
    for f, dz in ((.8, 1.4), (.5, 2.4), (.2, 2.9)):
        cur = [(c[0] + (x - c[0]) * f, c[1] + (y - c[1]) * f, h + dz) for x, y in list(poly.exterior.coords)[:-1]]
        for k in range(len(prev)): mb.face([prev[k], prev[(k + 1) % len(prev)], cur[(k + 1) % len(prev)], cur[k]], rm)
        prev = cur
    mb.face(prev, rm); toonify(mb.build('b%d' % idx, idx))

# ---------------- 랜드마크 설정·배정 ----------------
LMC.update({
    'ifc1': dict(glass='#86a8c8', line='#b7cbdd', flh=4.2, rise=16, sdir=(0.5, 0.86), facets=[(0.8, 0.6, .30, 15.0), (-0.7, -0.7, .55, 10.0)]),
    'ifc2': dict(glass='#86a8c8', line='#b7cbdd', flh=4.2, roofk='plain', rise=15, sdir=(-0.5, 0.86), facets=[(-0.8, 0.6, .30, 14.0), (0.7, -0.7, .55, 10.0)]),
    'ifc3': dict(glass='#7b9fc4', line='#b7cbdd', flh=4.2, roofk='oval', rise=14, sdir=(0.3, 0.95), hroof=279.0, htop=287.0, top='disc', facets=[(0.75, 0.66, .22, 17.0), (-0.75, 0.66, .50, 12.0), (0.0, -1.0, .62, 9.0)]),
    'conrad': dict(glass='#8fb0c9', line='#bccddc', flh=4.0, roofc='#4f555b', rise=12, sdir=(-0.8, 0.6), facets=[(-0.8, 0.6, .35, 13.0)]),
    'lg': dict(glass='#5b554c', line='#b9ad96', flh=3.8, bay=1.6, sp=.42, spc='#c9bda6', lobby=7.0, crownband=2.6, kit=2, var=.03, heli='tri'),
    'fki': dict(glass='#a9c0cb', line='#8ea5b0', flh=4.4, bay=1.5, sp=.42, spc='#4f6c86', hroof=245.5, lobby=10.0, kit=4, var=.03, roofk='solar'),
})
LMB = {'parc1': parc, 'parc2': parc, 'ifc1': crystal, 'ifc2': crystal, 'ifc3': crystal, 'conrad': crystal, 'lg': gtower, 'fki': gtower}   # 종류 이름은 그대로 landmark:<키>
def krx(b, idx):
    """[2차 위성뷰] 한국거래소: 모서리가 접힌 네모 평면. 옥상 가운데를 짙은 풀색 잔디 정원이 넓게 차지하고 그 둘레를 청회색 띠가 두른다. 바깥 옥상은 어두운 회갈색,
    네 변 가운데쯤에 초록 지붕의 작은 옥탑. 벽은 1차와 같은 돌 외장(CIVIC 색)."""
    poly = orient(P(b['rings']), 1.0); h = b['h']; mb = MB(); path, tw, th = finwall_tex('#cfcabd#46515b', '#cfcabd', '#46515b', shade('#cfcabd', 1.08), 2.4, 4.0)
    skin(mb, poly, 0.0, lambda x, y: h, mat_tex(path, 'fin_' + path), tw, th); flat_roof(mb, poly, h, shade('#cfcabd', 1.08), '#6f6a62')
    c_, ax_, Lx, Ly, mc = mrr_axes(poly); rc = np.array(mc).mean(axis=0); nv_ = np.array([-ax_[1], ax_[0]])
    obox(mb, rc, ax_, .36 * Lx, .36 * Ly, h, h + .7, mat_flat('#8f9ea9'), mat_flat('#a7b6c1')); obox(mb, rc, ax_, .36 * Lx - 2.6, .36 * Ly - 2.6, h + .7, h + .9, mat_flat('#41643a'))
    for su, sv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        q = rc + ax_ * su * (.44 * Lx) + nv_ * sv * (.44 * Ly)
        if poly.buffer(-3).contains(Point(*q)): obox(mb, q, ax_, 3.2, 3.2, h, h + 3.4, mat_flat('#d6d2c6'), mat_flat('#4f9a72'))
    toonify(mb.build('b%d' % idx, idx))
def fairmont(b, idx):
    """[3차 위성뷰] 페어몬트 앰배서더 서울(파크원 단지의 호텔 동, 더현대 남동쪽 모서리): 짙은 유리 타워, 옥상에 둥근 원판 헬리패드(회색 바탕, 흰 고리)."""
    poly = orient(P(b['rings']), 1.0); h = b['h']; mb = MB(); path, tw, th = grid_tex('parc', '#5f7890', '#8fa3b3', 1.5, 4.4, sp=.3, spc='#4c6076', var=.05)
    _lobby(mb, poly, 9.0, '#5f7890', '#b5382a', '#8fa3b3'); skin(mb, poly, 9.0, lambda x, y: h, mat_tex(path, 'gparc'), tw, th); capf(mb, poly, lambda x, y: h, mat_flat('#8f9296')); _parapet(mb, poly, h, '#4c6076')
    c, ax_, Lx, Ly, mc = mrr_axes(poly); rc = np.array(mc).mean(axis=0); nv = np.array([-ax_[1], ax_[0]]); ang0 = math.atan2(ax_[1], ax_[0]); fm = mat_flat('#c43a2a')
    # 붉은 기둥은 넣지 않았다: 평면이 네모가 아니라 기둥 자리를 위성뷰만으로 정할 수 없었다(저층 붉은 띠만).
    R = min(.40 * Ly, 11.0); mb.cyl((rc[0], rc[1], h), R * .45, 3.0, mat_flat('#7c8288'), n=16); mb.cyl((rc[0], rc[1], h + 3.0), R, 1.0, mat_flat('#6f757c'), mat_flat('#5d666f'), n=36)
    _annulus(mb, rc, h + 4.05, R * .50, R * .50 + max(.9, R * .09), mat_flat('#f6f6f1')); _annulus(mb, rc, h + 4.05, R * .96 - max(.8, R * .08), R * .96, mat_flat('#f6f6f1'))
    roof_kit(mb, poly.difference(Point(*rc).buffer(R + 1)).buffer(0), h, random.Random(b['seed']), 2)
    toonify(mb.build('b%d' % idx, idx))
def _roofpaint(col, inset=1.0, court=None):
    """finwall_bld 의 extra: 옥상 바닥을 칠한다(방수 초록·잔디 등). court = 가운데 어두운 태양광 뜰의 크기 비율."""
    def f(mb, poly, h):
        g = poly.buffer(-inset, join_style=2)
        for q in parts(g):
            if q.area > 20: capf(mb, orient(q, 1.0), lambda x, y: h + .07, mat_flat(col))
        if court:
            c_, ax_, Lx, Ly, mc = mrr_axes(poly); rc = np.array(mc).mean(axis=0); obox(mb, rc, ax_, court * Lx / 2, court * Ly / 2, h + .07, h + .5, mat_flat('#3d4854'), mat_flat('#465364'))
    return f
# [3차 위성뷰] 국회 부속동 옥상: 도서관 = 초록 방수 바닥, 소통관 = 잔디 옥상(가운데 뜰은 OSM 윤곽의 구멍 그대로), 의원회관 = 잔디 조각이 넓게 덮인 옥상(세부는 단순화), 의정관·박물관은 확인 못 해 그대로
CIVX = {'국회도서관': _roofpaint('#4f9a72'), '국회소통관': _roofpaint('#5d6f42', 1.5), '국회의원회관': _roofpaint('#66774a', 4.0)}
LMN = {'전경련회관 컨퍼런스센터': (fki_hall, 'landmark:fki_hall'), '페어몬트 앰배서더 서울': (fairmont, 'tower'), 'KRX한국거래소서울사무소': (krx, 'landmark:KRX한국거래소서울사무소')}   # 이름으로 배정하는 부속 건물(새 종류 이름)

# ---------------- 국회의사당(gen_area.py 의 것을 가져와 돔만 고침) ----------------
def assembly(lm, idx):
    """국회의사당 본관(전용). [랜드마크 개선] 사진 8장 대조: 돔 색(연한 옥색)·높이, 돔 받침의 네모 창 띠만 고침.  근거: 국가기록원·위키백과 — 길이 122 m·폭 81 m, 기둥 24개(앞·뒤 8, 양옆 4 = 모서리 포함 측면 6), 팔각 화강암 기둥,
    돔 밑지름 64 m·동판(청록), 사진 3장 — 정면은 남동(앞 잔디광장·분수 쪽), 기둥 바깥 열주 + 두꺼운 평판 처마, 돔은 흰 받침 위 낮은 반구, 정면 가운데 짙은 갈색 격자.
    추정: 높이(처마 36.5 m, 돔 꼭대기 ≈57 m — 정면 사진 비례), 돔 높이, 기단 1.4 m 와 계단 형태, 본체 들여쌓기 7 m."""
    poly = unary_union([P(r) for r in lm['rings']]); cen = np.array(poly.centroid.coords[0]); a = math.radians(38.0)
    ax_ = np.array([math.cos(a), math.sin(a)]); nv = np.array([-math.sin(a), math.cos(a)])  # nv = 북서(뒤), -nv = 남동(정면)
    mb = MB(); gran = mat_flat('#d9d4c8'); white = mat_flat('#ebe8e0'); Z0 = 1.4
    pod = poly.buffer(0)  # 기단 = OSM 윤곽(1.4 m)
    for g in parts(pod):
        g = orient(g, 1.0); capf(mb, g, lambda x, y: Z0, mat_flat('#cfc8b9')); skin(mb, g, 0.0, lambda x, y: Z0, mat_flat('#bdb6a7'), 1, 1)
    # 정면 계단: 기단 앞 가장자리(정면 축 위)
    ray = LineString([cen, cen - nv * 200]); hit = ray.intersection(pod.exterior)
    if not hit.is_empty:
        hp = np.array(min([hit] if hit.geom_type == 'Point' else list(getattr(hit, 'geoms', [])), key=lambda q: Point(*cen).distance(q)).coords[0])
        for k in range(5): obox(mb, hp - nv * (k + .5) * .45, ax_, 30.0, .45 / 2 + .02, 0.0, Z0 - k * .28, gran)
    # 본체(들여쌓기): 108×67, 높이 Z0+27
    body = Polygon([tuple(cen + ax_ * su * 54 + nv * sv * 33.5) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    tex = f'{TEXD}/asm.png'
    if not os.path.exists(tex):
        bay, flh = 1.8, 4.3; tw_, th_ = int(bay * 8 * RPPM), int(flh * 2 * RPPM); im = Image.new('RGB', (tw_, th_), '#dcd7cc'); d = ImageDraw.Draw(im)
        for f in range(2):
            for k in range(8): x0_, y0_ = int(k * bay * RPPM), int(f * flh * RPPM); d.rectangle([x0_ + 9, y0_ + 22, x0_ + int(bay * RPPM) - 9, y0_ + int(flh * RPPM) - 26], fill='#46525e'); d.line([(x0_ + int(bay * RPPM / 2), y0_ + 22), (x0_ + int(bay * RPPM / 2), y0_ + int(flh * RPPM) - 26)], fill='#9aa3a8', width=2)
        im.save(tex)
    skin(mb, orient(body, 1.0), Z0, lambda x, y: Z0 + 27.0, mat_tex(tex, 'asm'), 1.8 * 8, 4.3 * 2)
    fc = cen - nv * 33.6  # 정면 가운데 갈색 격자(두 기둥 사이 한 칸) + 아래 유리 현관
    grille = f'{TEXD}/asm_g.png'
    if not os.path.exists(grille):
        im = Image.new('RGB', (128, 128), '#6b4f3a'); d = ImageDraw.Draw(im)
        for k in range(0, 128, 8): d.line([(k, 0), (k, 128)], fill='#4a3628', width=2); d.line([(0, k), (128, k)], fill='#4a3628', width=1)
        im.save(grille)
    gm_ = mat_tex(grille, 'asm_g')
    for s_, z0_, z1_, m_ in ((1, Z0 + 7.0, Z0 + 26.0, gm_), (1, Z0, Z0 + 7.0, mat_flat('#3d4c58'))):
        p0, p1 = fc - ax_ * 8.0, fc + ax_ * 8.0; mb.face([(*p0, z0_), (*p1, z0_), (*p1, z1_), (*p0, z1_)], m_, [(0, 0), (4, 0), (4, (z1_ - z0_) / 4), (0, (z1_ - z0_) / 4)])
    # 열주 24: 앞·뒤 8, 양옆은 모서리 포함 6
    ZC = 32.0; us = np.linspace(-59.0, 59.0, 8); vs = np.linspace(-38.9, 38.9, 6); cols = set()
    for u in us:
        for sv in (-1, 1): cols.add((round(u, 2), round(sv * 38.9, 2)))
    for v in vs:
        for su in (-1, 1): cols.add((round(su * 59.0, 2), round(v, 2)))
    assert len(cols) == 24
    for u, v in cols: p_ = cen + ax_ * u + nv * v; mb.cyl((p_[0], p_[1], Z0), 1.55, ZC - Z0, white, n=8)  # 팔각 기둥
    # 평판 처마(엔태블러처) + 밑면 띠
    obox(mb, cen, ax_, 62.5, 41.5, ZC, ZC + 4.5, white, mat_flat('#cfccc4'))
    for su, sv, hx, hy in ((0, 1, 62.2, .45), (0, -1, 62.2, .45), (1, 0, .45, 40.3), (-1, 0, .45, 40.3)): obox(mb, cen + ax_ * su * 61.75 + nv * sv * 40.75, ax_, hx, hy, ZC + 4.5, ZC + 5.4, white, mat_flat('#efece6'))   # 지붕 난간
    obox(mb, cen, ax_, 61.0, 40.0, ZC - .6, ZC, mat_flat('#c9c4b8'))
    # [2차 위성뷰] 돔 둘레 옥상은 파란 방수 바닥이고 가장자리만 화강암색 테다. 돔 양옆(긴 축 방향)에 길쭉한 어두운 채광정이 하나씩, 그 양 끝에 흰 벽·파란 지붕의 작은 옥탑 4개.
    obox(mb, cen, ax_, 59.6, 38.6, ZC + 4.5, ZC + 4.56, mat_flat('#4878a4')); _annulus(mb, cen, ZC + 4.6, 32.0, 34.2, mat_flat('#d9d4c8'), 48)   # [4차] 돔 받침 둘레의 밝은 돌 띠
    for su in (-1, 1):
        obox(mb, cen + ax_ * su * 39.5, ax_, 5.0, 17.0, ZC + 4.56, ZC + 4.62, mat_flat('#2e3b35'))
        for sv in (-1, 1): obox(mb, cen + ax_ * su * 39.5 + nv * sv * 21.0, ax_, 3.4, 3.4, ZC + 4.5, ZC + 7.6, mat_flat('#e6e6e0'), mat_flat('#5d89b6'))
        for t_ in (-.6, -.2, .2, .6): obox(mb, cen + ax_ * su * 39.5 + nv * t_ * 17.0, ax_, 5.0, .4, ZC + 4.62, ZC + 4.68, mat_flat('#8fa0a6'))   # [4차] 채광정 살
        _frame(mb, cen + ax_ * su * 39.5, ax_, 5.6, 17.6, ZC + 4.6, .7, mat_flat('#d9d4c8'))                                                       # 채광정 테
    # [2차 위성뷰] 앞 잔디마당 축 끝의 둥근 분수(위치는 OSM 의 원형 잔디 216.6 m, 반지름 14.8 m 에 맞춤): 밝은 돌 바닥 원 + 얕은 수반 + 가운데 조형물 받침(조형물 자체는 단순한 기둥)
    fc_ = cen - nv * 216.6; mb.cyl((fc_[0], fc_[1], 0.0), 14.6, .14, mat_flat('#cfc8b6'), n=40); mb.cyl((fc_[0], fc_[1], .14), 9.6, .55, mat_flat('#d8d4c8'), n=36)
    _disc(mb, fc_, .72, 8.8, mat_flat('#54aab4'), 36); mb.cyl((fc_[0], fc_[1], .14), 2.2, 1.6, mat_flat('#c2bdaf'), n=16); mb.cyl((fc_[0], fc_[1], 1.74), .9, 3.4, mat_flat('#a9a598'), n=10)
    obox(mb, cen, ax_, 54, 33.5, Z0 + 27.0, ZC - .6, mat_flat('#d2cdc2'))   # 본체 위와 처마 사이 벽
    # 돔: 흰 받침 2단 + 청록 동판 반구(리브)
    # [4차] 돔 껍질은 따로(mbd) 만들어 한 색 + 부드러운 음영(면마다 밝기가 달라 포스터라이즈에서 조각무늬가 됐다). 형태·ID 는 그대로
    RT = ZC + 4.5; mb.cyl((cen[0], cen[1], RT), 32.0, 2.4, white, mat_flat('#e2ded4'), n=48); mb.cyl((cen[0], cen[1], RT + 2.4), 29.8, 4.2, white, mat_flat('#e2ded4'), n=48)
    for k in range(32): a_ = 2 * math.pi * (k + .5) / 32; mb.box((cen[0] + 29.85 * math.cos(a_), cen[1] + 29.85 * math.sin(a_), RT + 3.6), .12, 1.5, 1.8, mat_flat('#59636b'), a_)   # [사진] 돔 받침 둘레의 작은 네모 창
    zb_ = RT + 6.6; Rb, Hd, NS = 29.2, 19.5, 32; prev = None; mbd = MB(); dc = [mat_flat('#a5d6c0'), mat_flat('#9bcdb6')]   # [사진] 연한 옥색 동판, 받침 위로 더 높이
    for j in range(9):
        t_ = j / 8; r_ = Rb * math.cos(t_ * math.pi / 2); z_ = zb_ + Hd * math.sin(t_ * math.pi / 2)
        ring = [(cen[0] + r_ * math.cos(2 * math.pi * k / NS), cen[1] + r_ * math.sin(2 * math.pi * k / NS), z_) for k in range(NS)]
        if prev:
            for k in range(NS): mbd.face([prev[k], prev[(k + 1) % NS], ring[(k + 1) % NS], ring[k]], dc[0])
        prev = ring
    for k in range(0, NS, 2):  # 리브 선
        pts_ = [(cen[0] + Rb * math.cos(t_ * math.pi / 2) * 1.004 * math.cos(2 * math.pi * k / NS), cen[1] + Rb * math.cos(t_ * math.pi / 2) * 1.004 * math.sin(2 * math.pi * k / NS), zb_ + Hd * math.sin(t_ * math.pi / 2)) for t_ in np.linspace(0, .97, 7)]
        for q0, q1 in zip(pts_[:-1], pts_[1:]): beam(mb, q0, q1, .35, mat_flat('#c6e8d8'))
    mb.cyl((cen[0], cen[1], zb_ + Hd - .2), 1.6, .9, white, n=12)
    toonify(mb.build('b_asm', idx)); od = mbd.build('b_asm_dome', idx); smooth_obj(od, 60.0); toonify(od, top=1.01)   # [5차] 돔: 면마다 3단계 계단 음영(꼭대기까지)
    return poly

# ---------------- 교각 ----------------
def _hexa(mb, q0, q1, z0, z1, m):
    for k in range(4): a, b = k, (k + 1) % 4; mb.face([(*q0[a], z0), (*q0[b], z0), (*q1[b], z1), (*q1[a], z1)], m)
    mb.face([(*p, z1) for p in q1], m)
def pier_wonhyo(mb, p, tg, nrm, w, zb, zt, pm):
    """원효대교(사진 3장): 둥근 기초 위에서 흰 다리 두 개가 교축 방향 앞뒤로 벌어져 올라가 상판을 받치는 V 자 교각."""
    p = np.array(p[:2], float); hw = w * .34; S_ = min(13.0, max(6.0, (zt - zb) * .95))
    rect = lambda cc, hl: [cc + tg * su * hl + nrm * sv * hw for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    zf = (WL + .9) if zb < 0 else .4
    for sgn in (-1, 1): _hexa(mb, rect(p + tg * sgn * 1.2, 1.3), rect(p + tg * sgn * S_, 1.1), zf, zt, pm)
    if zb < 0: mb.cyl((p[0], p[1], WL - .6), max(4.0, w * .5), 1.5, mat_flat('#d2cfc6'), mat_flat('#bdb9ae'), n=24)
def pier_seogang(mb, p, tg, nrm, w, zb, zt, pm):
    """서강대교(사진 3장): 네모난 콘크리트 기둥 한 쌍 + 머리 보."""
    p = np.array(p[:2], float)
    for o in (-w * .27, w * .27): c_ = p + nrm * o; obox(mb, c_, tg, 1.3, 1.7, zb, zt - 1.4, pm)
    obox(mb, p, tg, 1.5, w * .46, zt - 1.4, zt, pm)
PIERB = {'wonhyo': pier_wonhyo, 'seogang': pier_seogang}

# ---------------- [5차] gen_area.py 의 랜드마크 빌더에도 픽셀아트 재질 ----------------
_church0 = church
def church(b, idx): _church0(b, idx); toonify(bpy.data.objects.get('b%d' % idx))

# ---------------- [5차] KBS(사진 대조: 커먼스 'KBS Main Building in 2018', 'KBS Annex Building in 2018', 'KBS본관 전경') — 재질만 ----------------
# 신관(본관 옆 열주 건물, OSM 'KBS 신관' + 붙은 파트 4584): 밝은 회백색 네모 돌기둥이 층을 꿰뚫고, 기둥 사이는 짙은 유리(움푹), 꼭대기에 두꺼운 처마 띠.
# 별관(OSM 'KBS 별관'): 베이지 돌판 외장에 작은 네모 창이 줄지어 뚫린 타워(옥상 붉은·흰 송신탑은 형태라 넣지 않음).
# 이 건물들은 종류가 lowrise 라 굽기에서 잠그지 않는다(벽·지붕 모두 양식 패스 결과) — cond 는 다음 양식 패스의 조건 그림에만 쓰인다. 형상(modern)은 그대로, 벽 텍스처만 바꾼다.
KBSF = {4582: 'kbs_main', 4584: 'kbs_main', 4327: 'kbs_annex'}   # scene.json 의 건물 순번
def kbs_atlas(k):
    """modern() 의 벽 아틀라스와 같은 꼴(가로 5칸 × 세로 2줄, 칸 = 한 칸·한 층, 5번째 칸 = 민벽)."""
    p = f'{TEXD}/{k}.png'
    if os.path.exists(p): return p
    cw, ch = 96, 80; im = Image.new('RGB', (cw * 5, ch * 2), '#d9d7d0' if k == 'kbs_main' else '#d8ccb4'); d = ImageDraw.Draw(im)
    for row in range(2):
        for col in range(5):
            ox, oy = col * cw, row * ch
            if col == 4: d.rectangle([ox, oy + ch - 4, ox + cw - 1, oy + ch - 1], fill='#b9b6ad'); continue
            if k == 'kbs_main':   # 돌기둥(왼쪽 1/4) + 짙은 유리 + 위쪽 돌 띠, 유리 칸 경계 어두운 선
                d.rectangle([ox + 24, oy + 10, ox + cw - 1, oy + ch - 1], fill='#3a4651'); d.rectangle([ox + 24, oy + 10, ox + 27, oy + ch - 1], fill='#232b33')
                d.rectangle([ox + 24 + (cw - 24) // 2, oy + 10, ox + 25 + (cw - 24) // 2, oy + ch - 1], fill='#232b33'); d.rectangle([ox, oy + 6, ox + cw - 1, oy + 9], fill='#a9a69e')
            else:                 # 작은 네모 창 2개, 어두운 테
                for wx in (18, 58): d.rectangle([ox + wx - 2, oy + 20, ox + wx + 21, oy + 55], fill='#5d564a'); d.rectangle([ox + wx, oy + 22, ox + wx + 19, oy + 53], fill='#3d4650')
                d.rectangle([ox, oy + ch - 3, ox + cw - 1, oy + ch - 1], fill='#c4b89f')
    im.save(p); return p
_modern0 = modern
def modern(b, idx):
    _modern0(b, idx); k = KBSF.get(idx - 10000)
    if not (k and PXGRID): return
    o = bpy.data.objects.get('b%d' % idx)
    if o is None: return
    for sl in o.material_slots:
        if sl.material is not None and sl.material.name.startswith('tex_'): sl.material = mat_tex(kbs_atlas(k), k)
    toonify(o)
