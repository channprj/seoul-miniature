#!/usr/bin/env python3
"""6.25 cm/px 생성의 조정자: 공유 latent 하나를 들고, 스텝마다 창 작업을 큐(todo/)에 넣고 워커들의 x0 예측을 가중 평균한다.

  python3 hd_coord.py <run_dir> <src_dir> [--rect gx,gy,gw,gh] [--grids 00000000] [--ov 128] [--seed 11] [--prompt v3]

src_dir: guide_classes.png, final.png(현재 0.125 m/px 그림). run_dir 는 모든 워커가 같은 경로로 보는 공유 폴더.
방법 = 현재 그림을 2배 NEAREST 로 키워 조건으로 넣고(denoise 1.0), 창에 실제 있는 클래스만 언급한다.
다시 실행하면 이어서 한다(state/x_<step>.npy, 이미 있는 결과 파일은 건너뜀). 결과: <run_dir>/raw.png

새 조건·프롬프트(플래그, 없으면 위 기존 동작 그대로):
  python3 hd_coord.py <run_dir> --cond blk.png [--size 2688,1920] [--origin 4480,5120] (--prompt-file m1.txt | --prompt-module p.py)
  --cond <png>          생성 영역과 같은 크기(6.25 cm 픽셀)의 RGB 조건 그림. 키우지 않고 창 단위로 잘라 쓴다. src_dir 불필요.
  --size W,H            영역 크기(6.25 cm 픽셀). guide_classes.png 없이 쓸 때. --cond 와 함께면 그림 크기와 같아야 한다.
                        --cond 없이 쓰면 src_dir/final.png 를 --rect 의 gx,gy(0.5 m 단위) 부터 잘라 2배 NEAREST(기존 조건).
  --origin X,Y          영역 왼쪽 위의 전체 지도 좌표(6.25 cm). prompt_for 에 넘기는 좌표에만 더한다(기본 0,0).
  --prompt-file <txt>   모든 창에 이 프롬프트 하나.
  --prompt-module <py>  그 모듈의 prompt_for(x0, y0, tw, th) -> str 를 창마다 부른다(x0,y0 = origin + 창 위치, 전체 지도 좌표).
                        우선순위 module > file > 기존 클래스 기반 prompt(). 클래스 맵이 없으면 빈 창 skip 은 조건 창이 한 색일 때만.
"""
import argparse, json, math, os, time
from pathlib import Path
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser()
ap.add_argument('run'); ap.add_argument('src', nargs='?', default=''); ap.add_argument('--rect', default=''); ap.add_argument('--grids', default='00000000')
ap.add_argument('--cond', default=''); ap.add_argument('--size', default=''); ap.add_argument('--origin', default='0,0')
ap.add_argument('--prompt-file', default=''); ap.add_argument('--prompt-module', default='')
ap.add_argument('--ov', type=int, default=128); ap.add_argument('--seed', type=int, default=11); ap.add_argument('--prompt', default='v3')
ap.add_argument('--tw', type=int, default=1408); ap.add_argument('--th', type=int, default=1024); ap.add_argument('--stale', type=float, default=120)
a = ap.parse_args()
RUN, SRC = Path(a.run), Path(a.src)
for d in ('win', 'cond', 'todo', 'claimed', 'xin', 'done', 'state', 'png', 'log'): (RUN / d).mkdir(parents=True, exist_ok=True)
T0 = time.time()
def say(*s):
    line = f'[{time.strftime("%H:%M:%S")} +{time.time() - T0:.0f}s] ' + ' '.join(str(x) for x in s)
    print(line, flush=True); open(RUN / 'coord.log', 'a').write(line + '\n')

S = 8
OX, OY = [int(v) for v in a.origin.split(',')]
if a.cond or a.size:
    # 새 경로: 클래스 맵 없이 영역 크기를 조건 그림이나 --size 로 정한다. rect 는 0.5 m 단위로 meta 에만 남긴다.
    cond_img = Image.open(a.cond) if a.cond else None
    if cond_img is not None and cond_img.mode == 'RGBA':
        assert np.asarray(cond_img)[..., 3].min() == 255, 'cond 알파가 255 가 아닌 곳이 있다'
    W, H = [int(v) for v in a.size.split(',')] if a.size else cond_img.size
    if cond_img is not None: assert cond_img.size == (W, H), f'cond {cond_img.size} != size {(W, H)}'
    assert W % S == 0 and H % S == 0
    gx, gy = ([int(v) for v in a.rect.split(',')][:2] if a.rect else (0, 0)) if not a.cond else (0, 0)
    gw, gh = W // S, H // S; cls = None
    assert a.prompt_file or a.prompt_module, '클래스 맵이 없으면 --prompt-file 이나 --prompt-module 이 필요하다'
else:
    cond_img = None
    cls_full = np.array(Image.open(SRC / 'guide_classes.png'))
    gx, gy, gw, gh = [int(v) for v in a.rect.split(',')] if a.rect else (0, 0, cls_full.shape[1], cls_full.shape[0])
    cls = cls_full[gy:gy + gh, gx:gx + gw]
    W, H = gw * S, gh * S
fixed_prompt = open(a.prompt_file).read().strip() if a.prompt_file else ''
prompt_for = None
if a.prompt_module:
    import importlib.util
    _sp = importlib.util.spec_from_file_location('hd_prompt_module', a.prompt_module); _pm = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_pm)
    prompt_for = _pm.prompt_for
SRCINFO = {'cond': os.path.abspath(a.cond) if a.cond else '', 'origin': [OX, OY],
           'prompt_src': ('module:' + os.path.abspath(a.prompt_module)) if a.prompt_module else ('file:' + os.path.abspath(a.prompt_file)) if a.prompt_file else 'classes:' + a.prompt}
assert W % 16 == 0 and H % 16 == 0
TW, TH = min(a.tw, W), min(a.th, H); lw, lh = TW // 8, TH // 8; LW, LH = W // 8, H // 8

def prompt(c):
    n = c.size; f = {k: float((c == k).sum()) / n for k in range(12)}
    det, ban = [], []
    if f[8] + f[9] > 0.004: det.append("individual dark giwa roof tiles in neat rows with ridge lines, lattice bars on doors and windows, dancheong patterns under the eaves, stone platform blocks")
    if f[6] + f[7] > 0.004: det.append("window frames and mullions, facade panels, shop fronts and the existing rooftop items drawn sharper")
    if f[5] + f[1] + f[11] > 0.03:
        if a.prompt == 'v3':
            det.append("on the ground, crisp joints only where the picture already shows paving stones (the irregular bakseok flagstones of the palace courtyards and the stone walkways keep their exact pattern and extent)")
        else:
            det.append("faint stone paving joints on the bare ground")
        ban.append("The open courtyards and pavements are bare and stay bare")
    if f[2] > 0.004: det.append("crisp lane markings on the asphalt")
    if f[10] > 0.004: det.append("leaf clusters on the existing tree crowns")
    if f[3] > 0.01: det.append("fine dithered grass texture on the existing lawns")
    if f[4] > 0.002: det.append("small ripples on the existing water")
    if f[10] <= 0.004: ban.append("There are no trees in this picture: do not draw any tree, bush or planter")
    if f[3] <= 0.01: ban.append("There is no grass in this picture: do not draw any lawn or green patch")
    if f[0] > 0.02: ban.append("The flat pale blue-grey area is empty background outside the map: leave it exactly as it is, one flat colour")
    flat = "Keep plain areas plain and patterned areas patterned. " if a.prompt == 'v3' else "Keep every flat area the same flat colour. "
    return ("This picture is a low-resolution isometric pixel-art city map that has been enlarged, so it looks coarse and blocky. Redraw it as crisp, finely detailed pixel art at this higher resolution. "
            "Keep exactly the same composition and camera: every shape stays in the same place with the same outline, size and colour. " + flat
            + "Only add finer pixel detail inside the existing shapes: " + "; ".join(det) + ". "
            + ". ".join(ban) + (". " if ban else "")
            + "Do not add any new object, building, tree, person, vehicle or text, and do not remove anything. "
            "True pixel art with small square pixels, thin one-pixel dark outlines, limited muted palette, clean dithering, no blur, no gradients, no photographic texture.")

def grid(total, size, ov):
    if total <= size: return [0]
    n = math.ceil((total - ov) / (size - ov)); step = (total - size) / (n - 1)
    p = [int(round(i * step / 16)) * 16 for i in range(n)]; p[-1] = total - size
    return p
def shifted(base, total, size):
    if len(base) == 1: return [0]
    return sorted(set([0] + [int(round((p + q) / 2 / 16)) * 16 for p, q in zip(base, base[1:])] + [total - size]))

metaf = RUN / 'meta.json'
if metaf.exists():
    meta = json.load(open(metaf)); wins = meta['windows']
    assert meta['rect'] == [gx, gy, gw, gh] and meta['grids'] == a.grids, 'run_dir belongs to a different job'
    assert meta.get('src', {'cond': '', 'origin': [0, 0], 'prompt_src': 'classes:' + a.prompt}) == SRCINFO, f"run_dir 입력이 다르다: {meta.get('src')} != {SRCINFO}"
else:
    say('setup: cutting window images')
    if cond_img is not None: art = cond_img.convert('RGB')      # 키우지 않는다
    else: art = Image.open(SRC / 'final.png').convert('RGB').crop((gx * 4, gy * 4, (gx + gw) * 4, (gy + gh) * 4)).resize((W, H), Image.NEAREST)
    xs0, ys0 = grid(W, TW, a.ov), grid(H, TH, a.ov)
    sets = {0: (xs0, ys0)}
    if '1' in a.grids: sets[1] = (shifted(xs0, W, TW), shifted(ys0, H, TH))
    wins = []
    for g, (xs, ys) in sets.items():
        for y in ys:
            for x in xs:
                i = len(wins); crop = art.crop((x, y, x + TW, y + TH))
                if cls is not None:
                    c = cls[y // S:(y + TH) // S, x // S:(x + TW) // S]; skip = bool((c != 0).mean() <= 0.02)
                else:
                    c = None; skip = bool(np.asarray(crop).reshape(-1, 3).std(0).max() < 0.5)   # 한 색 창만
                crop.save(RUN / 'win' / f'w{i}.png', compress_level=1)
                if skip: p = ''
                elif prompt_for is not None: p = prompt_for(OX + x, OY + y, TW, TH)
                elif fixed_prompt: p = fixed_prompt
                else: p = prompt(c)
                wins.append({'id': i, 'x': x, 'y': y, 'grid': g, 'skip': skip, 'prompt': p})
    meta = {'rect': [gx, gy, gw, gh], 'grids': a.grids, 'W': W, 'H': H, 'tw': TW, 'th': TH, 'ov': a.ov, 'seed': a.seed, 'windows': wins}
    if cls is None or a.prompt_file or a.prompt_module or (OX, OY) != (0, 0): meta['src'] = SRCINFO   # 새 플래그를 쓴 run 만
    json.dump(meta, open(str(metaf) + '.tmp', 'w')); os.replace(str(metaf) + '.tmp', metaf)
say(f'canvas {W}x{H}, {len(wins)} windows ({sum(w["skip"] for w in wins)} empty), grids {a.grids}')

def now_fs():
    p = RUN / 'state' / '.probe'; p.write_text('x'); return p.stat().st_mtime
def requeue():
    t = now_fs(); n = 0
    for d in (RUN / 'claimed').iterdir():
        for f in d.iterdir():
            try:
                if t - f.stat().st_mtime > a.stale: os.rename(f, RUN / 'todo' / f.name); n += 1
            except OSError: pass
    if n: say(f'requeued {n} stale task(s)')
    return n
def put(name, task):
    tmp = RUN / 'todo' / (name + '.tmp'); json.dump(task, open(tmp, 'w')); os.replace(tmp, RUN / 'todo' / (name + '.json'))
def pending(name):
    if (RUN / 'todo' / (name + '.json')).exists(): return True
    return any((d / (name + '.json')).exists() for d in (RUN / 'claimed').iterdir())
def wait(tasks, label):
    """tasks: {name: task}. 결과 파일이 다 생길 때까지 기다린다. 큐에서 사라졌는데 결과가 없는 작업은 다시 넣는다."""
    stats = {'requeued': 0}; t0 = time.time(); last = 0
    while True:
        left = [n for n, t in tasks.items() if not os.path.exists(t['out'])]
        if not left: break
        if time.time() - last > 15:
            stats['requeued'] += requeue(); last = time.time()
            for n in left:
                if not pending(n) and not os.path.exists(tasks[n]['out']): put(n, tasks[n])
            say(f'{label}: {len(tasks) - len(left)}/{len(tasks)}')
        time.sleep(1)
    say(f'{label}: done {len(tasks)} in {time.time() - t0:.0f}s')
    return stats

# ── 조건 인코딩
enc = {}
for w in wins:
    out = str(RUN / 'cond' / (f"w{w['id']}_x0.npy" if w['skip'] else f"w{w['id']}.pt"))
    w['cond'] = out
    if not os.path.exists(out):
        enc[f"enc_w{w['id']}"] = {'type': 'enc', 'image': str(RUN / 'win' / f"w{w['id']}.png"), 'skip': w['skip'], 'prompt': w['prompt'], 'out': out}
for n, t in enc.items(): put(n, t)
if enc: wait(enc, 'encode')

# ── 샘플링 (flow matching, shift 3.1, simple 스케줄 8스텝, euler)
steps = len(a.grids)
f_ = lambda t: 3.1 * t / (1 + 2.1 * t)
sig = [f_((1000 - int(i * 1000 / steps)) / 1000) for i in range(steps)] + [0.0]
def wmask(w):
    def axis(n, at0, at1):
        r = np.clip((np.arange(n, dtype=np.float32) + 0.5) / (a.ov / 8), None, 1.0); m = np.ones(n, np.float32)
        if not at0: m = np.minimum(m, r)
        if not at1: m = np.minimum(m, r[::-1])
        return np.maximum(m, 1e-4)
    return axis(lh, w['y'] == 0, w['y'] + TH >= H)[:, None] * axis(lw, w['x'] == 0, w['x'] + TW >= W)[None, :]
have = sorted(int(p.stem.split('_')[1]) for p in (RUN / 'state').glob('x_*.npy'))
if have:
    i0 = have[-1]; x = np.load(RUN / 'state' / f'x_{i0}.npy'); say(f'resume at step {i0}')
else:
    i0 = 0; x = np.random.default_rng(a.seed).standard_normal((1, 16, 1, LH, LW), dtype=np.float32)
    np.save(RUN / 'state' / 'x_0.npy', x)
for i in range(i0, steps):
    g = int(a.grids[i]); tasks = {}
    for w in wins:
        if w['grid'] != g or w['skip']: continue
        ly, lx = w['y'] // 8, w['x'] // 8
        xi = str(RUN / 'xin' / f"s{i}_w{w['id']}.npy"); out = str(RUN / 'done' / f"s{i}_w{w['id']}.npy")
        if not os.path.exists(out):
            np.save(xi + '.tmp.npy', np.ascontiguousarray(x[..., ly:ly + lh, lx:lx + lw])); os.replace(xi + '.tmp.npy', xi)
        tasks[f"den_s{i}_w{w['id']}"] = {'type': 'den', 'x': xi, 'cond': w['cond'], 'sigma': sig[i], 'out': out}
    for n, t in tasks.items():
        if not os.path.exists(t['out']): put(n, t)
    wait(tasks, f'step {i + 1}/{steps} (sigma {sig[i]:.3f})')
    acc = np.zeros_like(x); ws = np.zeros((LH, LW), np.float32)
    for w in wins:
        if w['grid'] != g: continue
        ly, lx = w['y'] // 8, w['x'] // 8; m = wmask(w)
        den = np.load(w['cond']) if w['skip'] else np.load(RUN / 'done' / f"s{i}_w{w['id']}.npy")
        acc[..., ly:ly + lh, lx:lx + lw] += den * m; ws[ly:ly + lh, lx:lx + lw] += m
    assert ws.min() > 0
    x0 = acc / ws
    x = x + (x - x0) / sig[i] * (sig[i + 1] - sig[i])
    np.save(RUN / 'state' / f'x_{i + 1}.tmp.npy', x); os.replace(RUN / 'state' / f'x_{i + 1}.tmp.npy', RUN / 'state' / f'x_{i + 1}.npy')
    for p in list((RUN / 'xin').glob(f's{i}_*')) + list((RUN / 'done').glob(f's{i}_*')) + [RUN / 'state' / f'x_{i}.npy']:
        try: p.unlink()
        except OSError: pass

# ── 디코드(창 단위) 후 픽셀에서 이어 붙임
dec = {}
for w in wins:
    if w['grid'] != 0: continue
    ly, lx = w['y'] // 8, w['x'] // 8
    xi = str(RUN / 'xin' / f"dec_w{w['id']}.npy"); out = str(RUN / 'png' / f"w{w['id']}.png")
    if not os.path.exists(out):
        np.save(xi + '.tmp.npy', np.ascontiguousarray(x[..., ly:ly + lh, lx:lx + lw])); os.replace(xi + '.tmp.npy', xi)
        put(f"dec_w{w['id']}", {'type': 'dec', 'x': xi, 'out': out})
    dec[f"dec_w{w['id']}"] = {'type': 'dec', 'x': xi, 'out': out}
wait(dec, 'decode')
say('blending')
acc = np.zeros((H, W, 3), np.float32); ws = np.zeros((H, W, 1), np.float32)
def pmask(w):
    def axis(n, at0, at1):
        r = np.clip((np.arange(n, dtype=np.float32) + 0.5) / a.ov, None, 1.0); m = np.ones(n, np.float32)
        if not at0: m = np.minimum(m, r)
        if not at1: m = np.minimum(m, r[::-1])
        return np.maximum(m, 1e-4)
    return (axis(TH, w['y'] == 0, w['y'] + TH >= H)[:, None] * axis(TW, w['x'] == 0, w['x'] + TW >= W)[None, :])[..., None]
for w in wins:
    if w['grid'] != 0: continue
    im = np.asarray(Image.open(RUN / 'png' / f"w{w['id']}.png").convert('RGB'), np.float32); m = pmask(w)
    acc[w['y']:w['y'] + TH, w['x']:w['x'] + TW] += im * m; ws[w['y']:w['y'] + TH, w['x']:w['x'] + TW] += m
acc /= ws
Image.fromarray(np.clip(acc + 0.5, 0, 255).astype(np.uint8)).save(RUN / 'raw.png', compress_level=1)
say('wrote', RUN / 'raw.png')
