# 타일을 이어 전체 조건 그림·ID·깊이를 만든다.
import json, glob, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
W, H, TW, TH = 22016, 13568, 2752, 1696
for suf, mode in (('', 'RGB'), ('_id', 'RGB'), ('_z', 'RGB')):
    out = Image.new(mode, (W, H))
    for j in range(8):
        for i in range(8): out.paste(Image.open(f'full/t_{i}_{j}{suf}.png').convert(mode), (i * TW, j * TH))
    out.save(f'full/cond{suf}.png'); print('saved', suf)
meta = {}
for f in glob.glob('full/t_*_meta.json'): meta.update(json.load(open(f)))
json.dump(meta, open('full/meta.json', 'w')); print('ids', len(meta))
