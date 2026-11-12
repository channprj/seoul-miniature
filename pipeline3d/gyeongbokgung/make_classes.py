# ID 패스 + 지면 클래스 → 0.5 m 클래스 맵(프롬프트 분기용)과 6.25 cm 클래스 맵.
import json, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
a = np.array(Image.open('full/cond_id.png').convert('RGB')); ids = a[..., 0].astype(np.uint16) * 256 + a[..., 1]; del a
meta = json.load(open('full/meta.json')); g = np.array(Image.open('ground_class.png'))
lut = np.zeros(65536, np.uint8); T = {'hanok': 7, 'lowrise': 6, 'midrise': 6, 'tower': 8, 'palace': 9, 'khs': 9, 'wall': 10, 'tree': 11}
for k, v in meta.items(): lut[int(k)] = T.get(v, 0)
G = np.zeros(256, np.uint8)
for k, v in {3: 1, 12: 1, 4: 2, 5: 3, 6: 4, 15: 4, 14: 5, 7: 0}.items(): G[k] = v
c = lut[ids]; c = np.where(ids <= 1, G[g], c).astype(np.uint8)
Image.fromarray(c).save('full/classes_0625.png'); Image.fromarray(c[4::8, 4::8]).save('full/classes_05m.png')
print({int(k): int(v) for k, v in zip(*np.unique(c[4::8, 4::8], return_counts=True))})
