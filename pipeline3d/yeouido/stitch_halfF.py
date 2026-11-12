# [5차] 판 F 12.5 cm 직접 렌더 타일(8×8, 2752×1696)을 이어 halfF/ 에 (stitch_full.py 의 사본, 판·격자만 바꿈)
# [3차] 판 C 6.25 cm 타일(16×16, 2752×1696)을 이어 cond.png·cond_id.png·cond_z.png·meta.json 을 만들고, 타일 결함을 점검한다.
# 사용(yeouido 폴더에서): python stitch_halfF.py [--check-only]
# 점검: 자홍(#ff00ff 근처) 픽셀, ID 0(빈) 픽셀, meta 에 없는 ID, 빈 타일(색 표준편차≈0), 타일 경계 단차(경계 열/행 차이 ÷ 바로 안쪽 열/행 차이),
#       깊이 기준(z0·step) 이 타일마다 같은지. 결과는 full/stitch_report.json.
import json, sys, os, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
D = os.environ.get('YD_PASS', 'halfF'); NI, NJ, TW, TH = 8, 8, 2752, 1696; W, H = NI * TW, NJ * TH   # 다른 지역: YD_PASS=<타일 폴더>, 판·px 는 타일 meta 에서 읽는다
check_only = '--check-only' in sys.argv
rep = {'tiles': {}, 'seams': {}}; meta = {}; depth = None; bad = []
small = Image.new('RGB', (W // 4, H // 4))
for j in range(NJ):
    for i in range(NI):
        t = f'{D}/t_{i}_{j}'; m = json.load(open(t + '_meta.json'))
        dd = (m['depth']['z0'], m['depth']['step'])
        if depth is None: depth = m['depth']
        elif dd != (depth['z0'], depth['step']): bad.append(f'{t}: depth 기준 다름 {dd}')
        meta.update(m['ids'])
        a = np.asarray(Image.open(t + '.png').convert('RGB')); ida = np.asarray(Image.open(t + '_id.png').convert('RGB'))
        assert a.shape == (TH, TW, 3), (t, a.shape)
        ids = ida[..., 0].astype(np.int32) * 256 + ida[..., 1]
        mag = int(((a[..., 0] > 225) & (a[..., 1] < 50) & (a[..., 2] > 225)).sum())
        u = np.unique(ids); unk = [int(x) for x in u if str(int(x)) not in m['ids'] and x != 0]
        r = dict(magenta=mag, id0=int((ids == 0).sum()), unknown_ids=unk, std=round(float(a.reshape(-1, 3).std(0).mean()), 2))
        if mag or r['id0'] or unk or r['std'] < 3: bad.append(f'{t}: {r}')
        rep['tiles'][f'{i}_{j}'] = r
        small.paste(Image.fromarray(a).reduce(4), (i * TW // 4, j * TH // 4))
small.save(f'{D}/cond_05m.png'); print('small saved', flush=True)
for suf in ('', '_id', '_z'):
    big = np.zeros((H, W, 3), np.uint8)
    for j in range(NJ):
        for i in range(NI): big[j * TH:(j + 1) * TH, i * TW:(i + 1) * TW] = np.asarray(Image.open(f'{D}/t_{i}_{j}{suf}.png').convert('RGB'))
    if suf in ('', '_id'):  # 경계 단차: 경계 양쪽 열(행)의 차이를, 바로 안쪽 이웃 열(행) 차이와 비교. ID 는 '다른 ID' 비율
        def df(x, y): return (x != y).any(-1).mean() if suf == '_id' else np.abs(x.astype(np.int16) - y.astype(np.int16)).mean()
        vs = [(df(big[:, k * TW - 1], big[:, k * TW]), df(big[:, k * TW - 2], big[:, k * TW - 1]), df(big[:, k * TW], big[:, k * TW + 1])) for k in range(1, NI)]
        hs = [(df(big[k * TH - 1], big[k * TH]), df(big[k * TH - 2], big[k * TH - 1]), df(big[k * TH], big[k * TH + 1])) for k in range(1, NJ)]
        rep['seams'][suf or 'color'] = {'vertical': [[round(float(v), 4) for v in x] for x in vs], 'horizontal': [[round(float(v), 4) for v in x] for x in hs],
                                        'max_ratio': round(float(max(b / max(1e-6, (c + d) / 2) for b, c, d in vs + hs)), 3)}
        print('seam', suf or 'color', rep['seams'][suf or 'color']['max_ratio'], flush=True)
    if not check_only:
        Image.fromarray(big).save(f'{D}/cond{suf}.png', compress_level=3); print('saved', suf, flush=True)
    del big
json.dump({'ids': meta, 'board': m['board'], 'board_def': m['board_def'], 'size': [W, H], 'render_px_m': m['render_px_m'], 'px_m': m['render_px_m'],
           'board_def_note': 'board_def 의 W·H 는 6.25 cm 기준(44032×27136). 12.5 cm px → 화면 m: u = SX0 + X·0.125, v = SY1 − Y·0.125', 'source': f"직접 렌더(gen_area.py {m['board']}, P3D_PXR={m['render_px_m']})", 'tiles': [NI, NJ, TW, TH],
           'id': 'pass_index = R*256+G (cond_id.png)', 'depth': depth}, open(f'{D}/meta.json', 'w'), ensure_ascii=False)
rep['bad'] = bad; json.dump(rep, open(f'{D}/stitch_report.json', 'w'), ensure_ascii=False, indent=1)
print('ids', len(meta), 'bad', len(bad)); [print(' ', b) for b in bad[:40]]
