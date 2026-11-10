#!/usr/bin/env python3
"""밑그림 전체를 2배 타일로 나눠 생성 장비에서 다시 그리고, 타일별 색 검사 후 실패분만 재시도해서 이어 붙인다.

  python3 pipeline/run_tiles.py <guide_dir> <work_dir> <tag> [--seed 11] [--retries 3] [--only r1c2,r0c0]

guide_dir: make_guide.py 출력(guide_color.png, guide_classes.png). 결과: <work_dir>/<tag>_full.png (5504×3392)
생성 장비 쪽은 pipeline/gen_server.sh up 으로 서버가 떠 있어야 한다. ssh 별칭은 GEN_SSH_HOST(기본 genbox).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from prompts import prompt_for  # noqa: E402

HOST = os.environ.get('GEN_SSH_HOST', 'genbox')
REMOTE = os.environ.get('GEN_REMOTE_DIR', '/srv/gen/redraw')
HERE = Path(__file__).parent

ap = argparse.ArgumentParser()
ap.add_argument('guide'); ap.add_argument('work'); ap.add_argument('tag')
ap.add_argument('--seed', type=int, default=11); ap.add_argument('--retries', type=int, default=3)
ap.add_argument('--only', default=''); ap.add_argument('--steps', type=int, default=8); ap.add_argument('--scale', type=int, default=2); ap.add_argument('--ov', type=int, default=224)
a = ap.parse_args()
guide, work = Path(a.guide), Path(a.work)
(work / 'in').mkdir(parents=True, exist_ok=True); (work / 'gen').mkdir(exist_ok=True)

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout

sh(sys.executable, str(HERE / 'tiles.py'), 'split', str(guide / 'guide_color.png'), str(work / 'in'), a.tag, '--scale', str(a.scale), '--ov', str(a.ov))
meta = json.load(open(work / 'in' / f'{a.tag}_tiles.json'))
cls = np.array(Image.open(guide / 'guide_classes.png'))
kinds = np.array(Image.open(guide / 'guide_kinds.png')) if (guide / 'guide_kinds.png').exists() else None
S = a.scale

def tile_cls(t):
    return cls[t['y'] // S:(t['y'] + meta['th']) // S, t['x'] // S:(t['x'] + meta['tw']) // S]

def tile_kind(t):
    return None if kinds is None else kinds[t['y'] // S:(t['y'] + meta['th']) // S, t['x'] // S:(t['x'] + meta['tw']) // S]

def qa(t, path):
    """클래스별 평균색이 말이 되는지 본다. 문제 설명 목록을 돌려준다(비면 통과)."""
    c = tile_cls(t)
    im = np.asarray(Image.open(path).convert('RGB').resize((c.shape[1], c.shape[0]), Image.BOX), np.float64)
    bad = []
    def mean(k):
        mk = c == k
        return im[mk].mean(axis=0) if mk.sum() > 400 else None
    r = mean(2)
    if r is not None and (r[2] - r[0] > 22 or r.max() - r.min() > 45 or r.mean() > 150): bad.append(f'road colour {r.round()}')
    w = mean(4)
    if w is not None and w[2] - w[0] < 20: bad.append(f'water colour {w.round()}')
    g = mean(3)
    if g is not None and not (g[1] > g[0] + 8 and g[1] > g[2] + 8): bad.append(f'lawn colour {g.round()}')
    e = mean(0)
    if e is not None and (e.max() - e.min() > 60): bad.append(f'empty background painted {e.round()}')
    # 물이 아닌 곳에 물색(파랑이 빨강보다 훨씬 강한 중간 밝기)이 넓게 칠해졌는지: 지어낸 연못·강
    from PIL import ImageFilter
    wd = np.asarray(Image.fromarray(((c == 4) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    blue = (im[..., 2] - im[..., 0] > 55) & (im[..., 2] > 130) & (im[..., 1] > 90)
    ok_area = wd | (c == 0) | (c == 6) | (c == 7)          # 건물 유리창은 파랄 수 있다
    frac = (blue & ~ok_area).sum() / c.size
    if frac > 0.008: bad.append(f'invented water {frac:.3f}')
    return bad

todo = [t for t in meta['tiles'] if (not a.only or f"r{t['r']}c{t['c']}" in a.only.split(','))]
todo = [t for t in todo if (tile_cls(t) != 0).mean() > 0.02]
skipped = [t for t in meta['tiles'] if (tile_cls(t) != 0).mean() <= 0.02]
print(f'{len(todo)} tiles to draw, {len(skipped)} empty')
sh('scp', '-q', *[str(work / 'in' / t['file']) for t in todo], f'{HOST}:{REMOTE}/in/')
for attempt in range(a.retries + 1):
    if not todo: break
    jobs = [{'name': f"{a.tag}_r{t['r']}c{t['c']}", 'image': t['file'], 'prompt': prompt_for(tile_cls(t), tile_kind(t)), 'seed': a.seed + attempt * 101, 'steps': a.steps} for t in todo]
    jf = work / f'{a.tag}_jobs_{attempt}.json'
    json.dump(jobs, open(jf, 'w'), indent=1)
    sh('scp', '-q', str(jf), f'{HOST}:{REMOTE}/')
    # 재시도 때 이전 출력과 섞이지 않게 원격의 같은 이름 출력은 지운다(우리 작업 폴더의 out/ 만)
    sh('ssh', HOST, f"cd {REMOTE} && rm -f " + ' '.join(f"out/{j['name']}_0*.png" for j in jobs) + f" && python3 gen_run.py {jf.name}")
    sh('scp', '-q', *[f"{HOST}:{REMOTE}/out/{j['name']}_00001_.png" for j in jobs], str(work / 'gen') + '/')
    failed = []
    for t in todo:
        bad = qa(t, work / 'gen' / f"{a.tag}_r{t['r']}c{t['c']}_00001_.png")
        if bad:
            print(f"  attempt {attempt} r{t['r']}c{t['c']}: {bad}"); failed.append(t)
    print(f'attempt {attempt}: {len(todo) - len(failed)} ok, {len(failed)} failed')
    todo = failed
if todo:
    print('STILL FAILING:', [f"r{t['r']}c{t['c']}" for t in todo])
# 빈 타일은 밑그림 그대로
for t in skipped:
    Image.open(work / 'in' / t['file']).save(work / 'gen' / f"{a.tag}_r{t['r']}c{t['c']}_00001_.png")
print(sh(sys.executable, str(HERE / 'tiles.py'), 'merge', str(work / 'in' / f'{a.tag}_tiles.json'), str(work / 'gen'), a.tag, str(work / f'{a.tag}_full.png')))
