#!/usr/bin/env python3
"""주요 랜드마크를 전용 프롬프트로 따로 그려, 이어 붙인 전체 그림 위에 그 건물 자리만 합성한다.

  python3 pipeline/landmarks.py <guide_dir> <work_dir> <full_in.png> <full_out.png> [--scale 4] [--seed 5] [--only a,b]

일반 타일은 "빌라·타워" 같은 종류 설명만 받기 때문에 광화문·경회루 같은 건물도 평범하게 그려진다.
여기서는 랜드마크를 타일 한가운데에 두고, 실제 생김새를 구체적으로 적은 문장을 프롬프트 앞에 넣는다.
합성은 그 건물 픽셀(조금 부풀린 범위)만 바꾸므로 주변과의 이음새가 작다.
guide_dir 에는 make_guide.py 가 쓴 landmarks.json, guide_bid.png 가 있어야 한다.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from prompts import prompt_for, HEAD  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HOST = os.environ.get('GEN_SSH_HOST', 'genbox')
REMOTE = os.environ.get('GEN_REMOTE_DIR', '/srv/gen/redraw')
TW, TH = 1408, 1024

# 실제 생김새. 모델이 이름만으로도 아는 건물이 많지만, 밑그림의 덩어리와 어긋나지 않게 형태를 말로 고정한다.
DESC = {
    'gwanghwamun': "Gwanghwamun, the main south gate of Gyeongbokgung Palace in Seoul: a tall pale granite base pierced by three arched gateways, crowned by a two-tier wooden gate pavilion with dark giwa tile hipped roofs, red columns and green-and-red dancheong, with long stone palace walls running off both sides",
    'geunjeongjeon': "Geunjeongjeon, the throne hall of Gyeongbokgung: a grand hall with a two-tier hip-and-gable dark giwa tile roof, red columns and lattice doors, standing on a wide two-level white granite terrace with carved stone balustrades and central stairs, in a stone-paved courtyard",
    'gyeonghoeru': "Gyeonghoeru, the royal banquet pavilion of Gyeongbokgung: a very large two-storey open pavilion with a broad hip-and-gable dark giwa tile roof, standing on rows of tall stone pillars on a rectangular stone island in the pond, joined to the shore by three stone bridges",
    'hyangwonjeong': "Hyangwonjeong: a small elegant hexagonal two-storey pavilion with a pointed hexagonal tile roof, on a round wooded island in the pond, reached by a long wooden footbridge",
    'folkmuseum': "the National Folk Museum of Korea: a tall five-tier pagoda-style tower with stacked dark tile roofs rising from a broad white stone base with a grand staircase, flanked by lower halls with traditional roofs",
    'palacemuseum': "the National Palace Museum of Korea: a long, low, wide museum of pale grey granite with a dark traditional giwa tile hip-and-gable roof, a row of square stone columns along the front and a very wide stone staircase leading up to it",
    'sejongcenter': "the Sejong Center for the Performing Arts: a massive pale grey granite cultural hall with a row of tall square columns along the front, wide entrance stairs and a flat stepped roof",
    'govcomplex': "Government Complex Seoul: a tall 19-storey beige slab office tower with regular vertical strips of windows and a flat roof with a rooftop plant floor, plus a lower matching annex",
    'mmca': "the National Museum of Modern and Contemporary Art, Seoul: low modern museum boxes clad in terracotta tiles and beige stone around open courtyards, beside an older red-brick building",
    'dongsipjagak': "Dongsipjagak: a small old corner watchtower, a square stone base with a single-storey pavilion and a dark tile hipped roof, standing alone at the road junction",
    'jibokjae': "Jibokjae, the royal library: a Chinese-influenced brick hall with a dark tile roof, linked by corridors to a two-storey octagonal pavilion and a side hall",
    'yeongbingwan': "Yeongbingwan state guest house: a stately pale granite hall with eighteen tall stone columns around it and a low hipped roof",
    'chunchugwan': "Chunchugwan press hall: a white-walled hall with a traditional gabled roof of clay tiles",
    'historymuseum': "the National Museum of Korean Contemporary History: a pale stone modern block with a glass curtain-wall front and a roof garden",
    'usembassy': "a plain 8-storey beige office block with a grid of small windows, set behind a perimeter wall",
    'kyobo': "the Kyobo Life building: a tall dark reddish-brown tiled office tower with tinted windows",
    'twintree': "Twin Tree Tower: two tall towers with rippling, faceted blue-green glass facades shaped like tree trunks",
    'gangnyeongjeon': "Gangnyeongjeon, the king's living quarters: a long hall with a dark giwa hip-and-gable roof on a stone platform with a front terrace",
    'gyotaejeon': "Gyotaejeon, the queen's quarters: a long hall with a dark giwa roof and no ridge beam, with a terraced flower garden and decorated chimneys behind it",
    'jagyeongjeon': "Jagyeongjeon: a hall with a dark giwa roof and a decorated orange brick flower wall",
    'ktwest': "the KT Gwanghwamun West building: a 15-storey 1980s office slab with a strict grid of deep-set square windows in pale concrete",
    'kteast': "the KT Gwanghwamun East building: a 25-storey modern office tower with a smooth blue-grey glass curtain wall",
    'police': "the Seoul Metropolitan Police Agency headquarters: a broad pale grey office block of about fifteen storeys with horizontal window bands and antennas on the roof",
    'jeongdok': "Jeongdok Public Library, a former school: three long white three-storey 1930s buildings with rows of tall windows, set in a garden with a fountain",
    'japanembassy': "a low construction site lot behind hoarding",
    'sarangchae': "Cheong Wa Dae Sarangchae: a two-storey modern exhibition hall of pale stone and glass with a flat overhanging roof",
    'artsonje': "Art Sonje Center: a compact four-storey modern art museum with a curved pale stone facade",
    'bluehouse': "the Blue House main building: a wide two-storey white hall with a hip-and-gable roof of bright blue glazed tiles and two smaller blue-roofed side wings",
}

ap = argparse.ArgumentParser()
ap.add_argument('guide'); ap.add_argument('work'); ap.add_argument('full_in'); ap.add_argument('full_out')
ap.add_argument('--scale', type=int, default=4); ap.add_argument('--seed', type=int, default=5); ap.add_argument('--only', default='')
ap.add_argument('--steps', type=int, default=8); ap.add_argument('--grow', type=int, default=5)
ap.add_argument('--refs', default='', help='refs.json 이 있는 폴더(선택). 있으면 그 사진을 image2 로 넣는다')
ap.add_argument('--no-composite', action='store_true')
ap.add_argument('--up', type=int, default=14)
ap.add_argument('--zoom', type=float, default=0, help='창 크기 배율을 고정(0.5 = 두 배 확대해 그린 뒤 줄여 붙임)')
ap.add_argument('--rect', action='store_true', help='건물 자리만이 아니라 창 전체를 바꾼다(가장자리는 흐리게)')
ap.add_argument('--tag', default='lm')
ap.add_argument('--reuse', action='store_true', help='lm_gen 에 이미 있는 그림을 쓰고 생성 장비에 접속하지 않는다')
ap.add_argument('--match', action='store_true', help='붙이기 전에 클래스별 평균색을 바탕 그림에 맞춘다(패치가 네모로 뜨지 않게)')
ap.add_argument('--anybld', action='store_true', help='창 안의 모든 건물·궁궐 구조물 자리를 바꾼다(담장 포함)')
ap.add_argument('--keep', default='', help='바탕 그림을 그대로 둘 클래스 번호들(예: 2 = 도로. 그려진 차가 딸려 오지 않게)')
a = ap.parse_args()
guide, work, S = Path(a.guide), Path(a.work), a.scale
(work / 'lm_in').mkdir(parents=True, exist_ok=True); (work / 'lm_gen').mkdir(exist_ok=True)

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout

lms = json.load(open(guide / 'landmarks.json'))
if a.only: lms = {k: v for k, v in lms.items() if k in a.only.split(',')}
lms = {k: v for k, v in lms.items() if k in DESC}
gcol = Image.open(guide / 'guide_color.png').convert('RGB')
cls = np.array(Image.open(guide / 'guide_classes.png'))
kinds = np.array(Image.open(guide / 'guide_kinds.png'))
bid = np.array(Image.open(guide / 'guide_bid.png'))
H, W = cls.shape
gw, gh = TW // S, TH // S                       # 밑그림 px 로 본 타일 크기

refs = json.load(open(Path(a.refs) / 'refs.json')) if a.refs else {}
jobs, rects, ref_files = [], {}, []
for key, lm in lms.items():
    # 건물이 기본 창(352x256 밑그림 px)보다 크면 창을 1.5배·2배로 넓힌다(그만큼 덜 세밀해진다)
    bx0, by0, bx1, by1 = lm['bbox']
    k = a.zoom or next((k for k in (1, 1.5, 2) if bx1 - bx0 + 40 <= gw * k and by1 - by0 + 40 <= gh * k), 2)
    cw, ch = int(gw * k), int(gh * k)
    mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
    x0 = int(min(max(0, round(mx - cw / 2)), W - cw)); y0 = int(min(max(0, round(my - ch / 2)), H - ch))
    rects[key] = (x0, y0, cw, ch)
    gcol.crop((x0, y0, x0 + cw, y0 + ch)).resize((TW, TH), Image.NEAREST).save(work / 'lm_in' / f'{a.tag}_{key}.png')
    base = prompt_for(cls[y0:y0 + ch, x0:x0 + cw], kinds[y0:y0 + ch, x0:x0 + cw])
    extra = f"The building at the centre of the image is {DESC[key]}. Paint it accurately and with care so that it is instantly recognisable, keeping its footprint and height from the block-out. "
    job = {'name': f'{a.tag}_{key}', 'image': f'{a.tag}_{key}.png', 'seed': a.seed, 'steps': a.steps}
    if key in refs:
        # 생김새는 글이 아니라 사진으로 알려 준다. 구도·시점은 밑그림(Picture 1)을 따른다.
        extra += ("Picture 2 is a reference photograph of that building. Take its real architecture from Picture 2: roof form, number of tiers, columns, wall and roof colours, facade pattern. "
                  "Redraw it in the pixel-art style, seen from the high oblique bird's-eye viewpoint and at the position and size given by the block-out in Picture 1. "
                  "Do not copy the photograph's ground-level viewpoint, sky, people, cars or surroundings. ")
        rf = f"ref_{key}.jpg"
        im = Image.open(Path(a.refs) / refs[key]['file']).convert('RGB'); im.thumbnail((1024, 1024)); im.save(work / 'lm_in' / rf, quality=92)
        ref_files.append(str(work / 'lm_in' / rf)); job['ref'] = rf
    job['prompt'] = HEAD + extra + base[len(HEAD):]
    jobs.append(job)
print(len(jobs), 'landmarks:', ', '.join(lms))
jf = work / 'lm_jobs.json'
json.dump(jobs, open(jf, 'w'), indent=1)
have = all((work / 'lm_gen' / f"{j['name']}_00001_.png").exists() for j in jobs)
if a.reuse and not have: raise SystemExit('--reuse: lm_gen 에 그림이 없다')
def sh_(*cmd):
    if not a.reuse: sh(*cmd)
sh_('scp', '-q', *[str(work / 'lm_in' / j['image']) for j in jobs], *ref_files, f'{HOST}:{REMOTE}/in/')
sh_('scp', '-q', str(jf), f'{HOST}:{REMOTE}/')
sh_('ssh', HOST, f"cd {REMOTE} && rm -f " + ' '.join(f"out/{j['name']}_0*.png" for j in jobs) + f" && python3 gen_run.py {jf.name}")
sh_('scp', '-q', *[f"{HOST}:{REMOTE}/out/{j['name']}_00001_.png" for j in jobs], str(work / 'lm_gen') + '/')

if a.no_composite: raise SystemExit('generated only (no composite)')
full = np.asarray(Image.open(a.full_in).convert('RGB'), np.float32).copy()
for key, lm in lms.items():
    x0, y0, cw, ch = rects[key]
    TWk, THk = cw * S, ch * S
    gen = np.asarray(Image.open(work / 'lm_gen' / f'{a.tag}_{key}_00001_.png').convert('RGB').resize((TWk, THk), Image.LANCZOS), np.float32)
    b, c = bid[y0:y0 + ch, x0:x0 + cw], cls[y0:y0 + ch, x0:x0 + cw]
    mk = (np.isin(b, lm['ids']) | bool(a.anybld)) & (c >= 6) & (c <= 9)
    ys, xs = y0 * S, x0 * S
    cu = np.repeat(np.repeat(c, S, axis=0), S, axis=1)
    if a.match:
        base = full[ys:ys + THk, xs:xs + TWk]
        for kc in (1, 2, 3, 5, 11):
            w = cu == kc
            if w.sum() > 3000: gen[w] += base[w].mean(axis=0) - gen[w].mean(axis=0)
    # 사진을 따라 그리면 탑·누각이 밑그림 덩어리보다 높이 솟는다. 위쪽으로 a.up px(밑그림) 만큼 더 덮는다.
    mu = mk.copy()
    for d in range(1, a.up + 1): mu[:-d] |= mk[d:]
    m = Image.fromarray((mu * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * a.grow + 1))
    m = m.resize((TWk, THk), Image.NEAREST).filter(ImageFilter.GaussianBlur(S * 1.5))
    al = (np.asarray(m, np.float32) / 255.0)[..., None]
    if a.rect: al = np.ones_like(al)
    # 타일 가장자리에서는 합성하지 않는다(잘린 건물이 어긋나지 않게)
    edge = np.ones((THk, TWk), np.float32); k = 24
    edge[:k] = edge[-k:] = 0; edge[:, :k] = edge[:, -k:] = 0
    if a.rect: edge = np.asarray(Image.fromarray((edge * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)), np.float32) / 255.0
    al *= edge[..., None]
    for kc in [int(v) for v in a.keep.split(',') if v]:
        keep = Image.fromarray(((cu == kc) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3))
        al *= 1 - (np.asarray(keep, np.float32) / 255.0)[..., None]
    full[ys:ys + THk, xs:xs + TWk] = full[ys:ys + THk, xs:xs + TWk] * (1 - al) + gen * al
Image.fromarray(np.clip(full, 0, 255).astype(np.uint8)).save(a.full_out)
print('wrote', a.full_out)
