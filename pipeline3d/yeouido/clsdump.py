# [3차] 판 전체 지면 분류 래스터(월드 xy) 덤프. gen_area.py 를 고치지 않고, 지면 분류를 그리는 구간(팔레트 직전)까지만 실행한다.
# 사용: P3D_PXR=0.5 P3D_W=5504 P3D_H=3392 P3D_GTEX=0.25 python clsdump.py C 0 0 full/ground_cls
# 출력: <출력>.png(L, 값 = gen_area 지면 분류 0–28), <출력>.json(gx0, gy1, GTEX: 픽셀 (i,j) 중심 = (gx0+(i+.5)·GTEX, gy1−(j+.5)·GTEX))
import os, sys, json
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_area.py')
code = open(src, encoding='utf-8').read(); cut = code.index('# 팔레트 + 월드 고정 잡음')
g = {'__file__': src, '__name__': '__clsdump__'}
exec(compile(code[:cut], src, 'exec'), g)
out = g['OUT']; g['CLS'].save(out + '.png')
json.dump({'gx0': g['gx0'], 'gy1': g['gy1'], 'GTEX': g['GTEX'], 'size': list(g['CLS'].size)}, open(out + '.json', 'w'))
print('dumped', g['CLS'].size, flush=True)
