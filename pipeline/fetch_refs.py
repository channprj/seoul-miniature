#!/usr/bin/env python3
"""랜드마크 참조 사진 후보를 위키미디어 공용에서 찾는다. 공개에 문제없는 라이선스만 남긴다.

  python3 pipeline/fetch_refs.py <out_dir> [key ...]

남기는 라이선스: 퍼블릭 도메인, CC0, CC BY(동일조건 없는 것), 공공누리 제1유형.
CC BY-SA 는 받지 않는다(다시 그린 그림에 동일조건이 따라올 수 있다).
결과: <out_dir>/<key>/NN.jpg (폭 960 표준 축소본, 요청 사이 2.5초 간격)와 <out_dir>/candidates.json (제목·저작자·라이선스·원본 주소).
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'landmark-ref-fetch/0.1 (personal research script)'}
SEARCH = {
    'gwanghwamun': ['Gwanghwamun gate', '광화문'], 'geunjeongjeon': ['Geunjeongjeon', '근정전'], 'gyeonghoeru': ['Gyeonghoeru', '경회루'],
    'hyangwonjeong': ['Hyangwonjeong', '향원정'], 'sejongcenter': ['Sejong Center for the Performing Arts', '세종문화회관'],
    'govcomplex': ['Government Complex Seoul', '정부서울청사'], 'mmca': ['National Museum of Modern and Contemporary Art Seoul', '국립현대미술관 서울관'],
    'dongsipjagak': ['Dongsipjagak', '동십자각'], 'jibokjae': ['Jibokjae', '집옥재'], 'folkmuseum': ['National Folk Museum of Korea building', '국립민속박물관'],
    'twintree': ['Twin Tree Tower Seoul', '트윈트리타워'], 'kyobo': ['Kyobo Building Gwanghwamun', '교보생명빌딩'], 'ktbuilding': ['KT Gwanghwamun Building', 'KT광화문빌딩'],
    'dtower': ['D Tower Seoul Gwanghwamun', '디타워 광화문'], 'historymuseum': ['National Museum of Korean Contemporary History', '대한민국역사박물관'], 'jeongdok': ['Jeongdok Public Library', '정독도서관'], 'yeongbingwan': ['Cheong Wa Dae Yeongbingwan', '청와대 영빈관'], 'chunchugwan': ['Chunchugwan Cheong Wa Dae', '청와대 춘추관'],
    'palacemuseum': ['National Palace Museum of Korea', '국립고궁박물관'], 'sarangchae': ['Cheong Wa Dae Sarangchae', '청와대 사랑채'], 'police': ['Seoul Metropolitan Police Agency building', '서울경찰청'],
    'ktwest': ['KT Gwanghwamun', 'KT 광화문 사옥'], 'twintree2': ['Twin Trees Tower', '트윈트리'], 'artsonje': ['Art Sonje Center', '아트선재센터'],
}

def ok_license(s):
    s = (s or '').strip()
    if re.search(r'SA|NC|ND', s): return False
    return bool(re.match(r'(CC0|Public domain|PD\b|PD-|CC BY \d|CC BY$|KOGL Type 1|Attribution)', s, re.I))

def get(url):
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e:
            time.sleep(8 + 10 * i); err = e
    raise err

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
keys = sys.argv[2:] or list(SEARCH)
cands = json.load(open(out / 'candidates.json')) if (out / 'candidates.json').exists() else {}
for key in keys:
    seen, lst = set(), []
    for q in SEARCH[key]:
        u = API + '?' + urllib.parse.urlencode({'action': 'query', 'format': 'json', 'generator': 'search', 'gsrsearch': q + ' filetype:bitmap', 'gsrnamespace': 6,
                                                'gsrlimit': 50, 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|size', 'iiurlwidth': 960})
        pages = json.loads(get(u)).get('query', {}).get('pages', {})
        for p in sorted(pages.values(), key=lambda p: p.get('index', 0)):
            ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {})
            lic = md.get('LicenseShortName', {}).get('value', '')
            if p['title'] in seen or not ok_license(lic) or ii.get('width', 0) < 900 or not ii.get('thumburl'): continue
            if not re.search(r'\.(jpe?g|png)$', p['title'], re.I): continue
            seen.add(p['title'])
            lst.append({'title': p['title'], 'license': lic, 'artist': re.sub(r'<[^>]+>', '', md.get('Artist', {}).get('value', '')).strip()[:120],
                        'page': ii.get('descriptionurl'), 'thumb': ii['thumburl'], 'credit': re.sub(r'<[^>]+>', '', md.get('Credit', {}).get('value', '')).strip()[:120]})
        time.sleep(1)
    lst = lst[:10]
    (out / key).mkdir(exist_ok=True)
    for i, c in enumerate(lst):
        f = out / key / f'{i:02d}.jpg'
        if not f.exists():
            f.write_bytes(get(c['thumb'])); time.sleep(2.5)
        c['file'] = str(f.relative_to(out))
    cands[key] = lst
    json.dump(cands, open(out / 'candidates.json', 'w'), ensure_ascii=False, indent=1)
    print(key, len(lst), [c['license'] for c in lst][:8], flush=True)
