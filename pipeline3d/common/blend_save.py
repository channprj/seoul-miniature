# 세운 장면을 공개용 .blend 한 파일로 저장한다(gen.py·gen_area.py 의 --save-blend 가 부른다).
#   - 이미지(입면 텍스처, 지면 그림)는 모두 파일 안에 넣는다(pack). 경로 칸은 '//textures/<이름>' 상대 경로로 바꾼다.
#   - 렌더 출력 경로는 '//render_' 로 바꾼다. 장면 사용자 속성 p3d_* 에 판·창·해상도·라이선스를 적는다.
#   - 압축 저장(compress=True, zstd). 절대 경로가 남지 않았는지는 `zstd -dc x.blend | strings | grep` 으로 따로 본다.
import os, re, json, io
import bpy

LICENSE = ('Scene data (c) OpenStreetMap contributors, ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/). '
           'Derived from OSM; see CREDITS.md of the seoul-miniature repository for the other sources.')

def _safe(name):
    s = re.sub(r'[^0-9A-Za-z._-]+', '_', name).strip('_') or 'img'
    return s if s.lower().endswith('.png') else s + '.png'

def _strip_png_text(data):
    """PNG 의 글 청크(tEXt·zTXt·iTXt — Blender 렌더 저장 때 .blend 경로 같은 메타데이터가 들어간다)를 뺀다. 픽셀 바이트는 그대로."""
    if data[:8] != b'\x89PNG\r\n\x1a\n': return data
    out, i = [data[:8]], 8
    while i + 8 <= len(data):
        n = int.from_bytes(data[i:i + 4], 'big'); t = data[i + 4:i + 8]; j = i + 12 + n
        if t not in (b'tEXt', b'zTXt', b'iTXt'): out.append(data[i:j])
        i = j
    return b''.join(out)

def save(path, props, readme=''):
    sc = bpy.context.scene
    sc.render.filepath = '_' * 1000; sc.render.filepath = '//render_'   # 긴 값으로 먼저 덮어 옛 출력 경로 조각을 지운다
    sc.render.threads_mode = 'AUTO'
    seen = set()
    for img in list(bpy.data.images):
        if img.source != 'FILE': continue
        if re.match(r'tmp_ground', img.name): img.name = 'ground.png'   # 렌더 때 작업 폴더에 쓴 지면 그림(이름에 작업 경로 조각이 들어 있다)
        if not img.packed_file: img.pack()
        nm = _safe(img.name)
        while nm in seen: nm = nm[:-4] + '_.png'
        seen.add(nm)
        # 경로 칸을 짧은 값으로 덮어써도 1024 바이트 칸의 뒤쪽에 옛 절대 경로 조각이 남아 파일에 그대로 쓰인다.
        # 그래서 넣은 바이트로 새 그림을 만들어(경로 칸이 처음부터 비어 있다) 바꿔 끼운다.
        data = _strip_png_text(bytes(img.packed_file.data)); w, h = img.size[:] if img.has_data else (1, 1)
        new = bpy.data.images.new(nm, max(w, 1), max(h, 1)); new.pack(data=data, data_len=len(data))
        new.source = 'FILE'; new.filepath_raw = '//textures/' + nm
        for pf in new.packed_files: pf.filepath = '//textures/' + nm
        new.colorspace_settings.name = img.colorspace_settings.name; new.alpha_mode = img.alpha_mode
        img.user_remap(new); bpy.data.images.remove(img); new.name = nm; new.reload()
    for coll in (bpy.data.materials, bpy.data.images, bpy.data.meshes, bpy.data.objects, bpy.data.node_groups, bpy.data.textures):
        for idb in coll:  # 이름에 든 임시 폴더 경로(예: 재질 'fin_/tmp/…/fin_x.png')를 파일 이름만 남긴다
            if '/' in idb.name: idb.name = re.sub(r'/(?:[^/]+/)+', '', idb.name)
    for k, v in props.items():
        sc['p3d_' + k] = v if isinstance(v, (int, float, str)) else json.dumps(v, ensure_ascii=False)
    sc['p3d_license'] = LICENSE
    sc['p3d_blender'] = bpy.app.version_string
    t = bpy.data.texts.get('README') or bpy.data.texts.new('README')
    t.clear(); t.write(readme or LICENSE)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True, relative_remap=True, copy=True)
    scrub(path)
    print('saved blend', path, os.path.getsize(path), 'bytes', flush=True)

# 저장된 바이트에는 Blender 가 칸을 짧은 값으로 바꾼 뒤에도 남긴 옛 문자열(작업 장비 절대 경로 등)이 섞여 들어간다.
# 어떤 속성으로도 읽히지 않는 죽은 바이트라서, 압축을 풀어 그런 문자열 조각을 0 으로 지우고 다시 압축한다.
# 지우는 기준: 절대 경로 머리(/home/ 등, 실행 장비의 홈 폴더) 또는 환경 변수 P3D_SCRUB(쉼표 목록, 5자 이상)의 낱말이 들어 있고 NUL 바로 뒤에서 시작하는 출력 가능 문자열 덩어리.
SCRUB = [b'/home/', b'/root/', b'/tmp/', b'/private/', b'/data/', b'/srv/', b'/mnt/', b'/var/folders'] + [os.path.expanduser('~').encode()] * (len(os.path.expanduser('~')) >= 5)   # 실행 장비의 홈 폴더도
def scrub(path):
    try: import zstandard
    except ImportError: print('scrub: zstandard 모듈이 없어 건너뜀', flush=True); return
    raw = open(path, 'rb').read()
    comp = raw[:4] == b'\x28\xb5\x2f\xfd'
    data = bytearray(zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw), read_across_frames=True).read() if comp else raw)   # Blender 는 여러 프레임으로 쓴다
    words = SCRUB + [w.strip().encode() for w in os.environ.get('P3D_SCRUB', '').split(',') if len(w.strip()) >= 5]
    pat = re.compile(rb'[\x20-\x7e]*(?:' + b'|'.join(re.escape(w) for w in words) + rb')[\x20-\x7e]*')
    n = 0
    for m in pat.finditer(bytes(data)):
        if m.group(0).startswith(b'//'): continue   # 살아 있는 상대 경로('//textures/…')는 두지만, 이 낱말이 든 경우는 없어야 한다
        if m.start() == 0 or data[m.start() - 1] != 0: continue   # 문자열 칸의 찌꺼기는 앞의 살아 있는 값의 NUL 바로 뒤에 온다. 그림 바이트 속 우연한 일치는 두지 않는다
        data[m.start():m.end()] = bytes(m.end() - m.start()); n += 1
    if n:
        out = zstandard.ZstdCompressor(level=3).compress(bytes(data)) if comp else bytes(data)
        open(path, 'wb').write(out)
    print('scrub', n, 'strings', flush=True)
