"""창별 양식 프롬프트. prompt_for(x0, y0, tw, th) -> str (6.25 cm 전체 좌표).
승인된 m1 문구(일반 동네)와 궁궐 창에서 검증된 문구를 그대로 쓰고, 창에 실제로 있는 것에 따라 문장 몇 개만 끼운다.
(11-11 시험: 문구를 길게 새로 쓴 분기판은 픽셀아트로 다시 그리지 않고 3D 렌더에 소품만 얹었다 → 폐기. 도로를 언급하면 도로를 지어낸다.)
full/classes_05m.png: 0 바탕지면 1 도로 2 광장·보도 3 잔디 4 마당 5 물 6 일반건물 7 한옥 8 타워 9 궁궐 10 담 11 나무"""
import os, numpy as np
from PIL import Image
_H = os.path.dirname(os.path.abspath(__file__)); _C = None
M1 = 'Repaint this plain 3D render as finished, detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. Keep the exact camera, scale and layout: every building keeps its exact footprint, outline, height, roof shape and main wall and roof colour, and stays exactly where it is. Do not add, remove, merge or move any building. Dark charcoal ribbed roofs are hanok, traditional Korean houses: grey-black giwa tile roofs with crisp tile rows, ridge lines and slightly upturned eaves, wooden posts and paper lattice doors. Hanok roofs are plain unbroken tile: no skylights, no windows, no objects on them. Flat-roofed 2-5 storey buildings are Seoul villa houses and shop-houses; each looks a little different. Add a moderate amount of small everyday detail, calm and tidy, not crowded. Each flat rooftop stays mostly open and keeps its green or grey colour, with only two to four small things on it, chosen from: a water tank, a couple of planters, a few brown onggi jars, a short laundry line, one parasol with a table, a satellite dish, a cooling unit, a solar panel. Walls get brick courses, varied window frames, a few balconies, air conditioner units and drain pipes; some ground floors have a shop front with a plain awning and a blank signboard. The pale ground stays plain quiet pavement with faint paving lines; along the building edges place only an occasional potted plant, bench, parked bicycle, street lamp or utility pole. Do not turn the ground into asphalt roads. No letters, no numbers, no writing, no logos anywhere. No cars, no trucks, no vans, no motor vehicles of any kind, no people. True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look, no smooth 3D shading), limited muted palette, clean dithering, short crisp shadows, no blur, no gradients, no photographic texture, no UI.'
PAL = 'Repaint this plain 3D render as finished, richly detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. This is a strict restyle: keep the exact camera, scale and layout. Every hall, roof, stone platform, wall, path and lawn stays exactly where it is, with the same outline, size and colour. Do not add, remove, merge or move anything. Do not invent buildings or objects in empty areas. The buildings are Korean palace halls: sweeping dark charcoal giwa tile roofs with crisp tile rows, white plastered ridge lines and gently upturned eaves, red wooden columns and green lattice doors, green-and-red dancheong under the eaves, standing on pale grey granite platforms with steps. The long thin tiled strips are palace walls: low stone-and-brick walls with visible masonry courses, capped with a narrow dark tile roof; keep every wall continuous and exactly in place, never turn it into a hedge, a road or a path. Sand-coloured areas are packed-earth palace courtyards, paler strips are stone walkways, light green areas are mown lawn with subtle dithered texture. Green lumps are trees: draw each as a pixel-art tree crown on the same spot. True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look, no smooth 3D shading), limited muted palette, clean dithering, short crisp shadows, no blur, no gradients, no photographic texture, no text, no people, no vehicles, no UI.'
TOWER = "Tall blocks with bands of windows are office towers: keep each tower's wall colour (pale walls stay pale) and its window bands as rendered; do not recolour a tower dark. "
TREE = "Green lumps on trunks are trees: draw each as a pixel-art tree crown on the same spot, the same size. "
PALIN = "Buildings with dark tiled roofs, red columns and stone platforms are historic Korean palace halls and gates: keep them exactly as rendered and add nothing on or around them. Long thin tiled strips are palace walls: stone walls capped with a narrow dark tile roof, kept continuous and exactly in place. "
GATE = "The large gate is a fortress-style stone gate: a tall pale granite block base pierced by three arched passages with red doors, topped by a two-tier wooden pavilion with dark tile roofs. Keep the stone base, its three arches and both roof tiers exactly as rendered; it is not a wooden hall. "
WOLDAE = "In front of the gate lies a long raised pale stone-paved ceremonial platform with stone balustrades and steps: keep the platform stone-paved (not grass), with its balustrades, steps and the stone guardian statue exactly as rendered. Bright green areas are flat mown lawn: keep their exact shape. "
NOTREE = "There are no trees in this view: do not draw any trees or bushes. "
PTREE = "Green lumps are trees: draw each as a pixel-art tree crown on the same spot. "
LAWN = "Bright green areas are flat mown lawn: keep them green and keep their exact shape. "
NOROAD = "Do not draw asphalt roads or lane markings on the pale ground. "
KEY = "The pale ground stays plain quiet pavement"
GATEBOX = (6060, 9260, 6610, 9840)   # 광화문 문루(6.25 cm 좌표, full2 조건 렌더에서 읽음)
WOLBOX = (5590, 9660, 6500, 10170)  # 월대
def prompt_for(x0, y0, tw, th):
    global _C
    if _C is None: _C = np.asarray(Image.open(os.path.join(_H, os.environ.get('P3D_FULL', 'full'), 'classes_05m.png')))
    c = _C[max(0, y0 // 8):(y0 + th) // 8, max(0, x0 // 8):(x0 + tw) // 8]; n = max(1, c.size); f = [float((c == k).sum()) / n for k in range(12)]
    def ov(b):   # 창이 상자 b 를 덮는 비율
        w = min(x0 + tw, b[2]) - max(x0, b[0]); h = min(y0 + th, b[3]) - max(y0, b[1])
        return max(0, w) * max(0, h) / float((b[2] - b[0]) * (b[3] - b[1]))
    gate = ov(GATEBOX) >= 0.35; gw = ov(WOLBOX) >= 0.5   # r1(11-11): 문이 안 보이는 이웃 창에도 문 문장이 들어가 문을 여러 채 지어냈다 → 실제로 보이는 창에만
    city = f[6] + f[7] + f[8]; pal = f[9] + f[10] + f[4]
    if pal > 0.03 and city < 0.03 and f[1] < 0.10 and f[0] < 0.10:   # 궁궐 창. 큰길·바깥 지면이 많은 창은 궁궐 문구가 전각을 지어낸다(gw2, 11-11) → 일반 문구 + PALIN
        p = PAL
        if gate: p = p.replace("The buildings are Korean palace halls:", GATE + "The other buildings are Korean palace halls:")
        if gw: p = p.replace("Sand-coloured areas", WOLDAE + "Sand-coloured areas")
        if f[11] < 0.002: assert PTREE in p; p = p.replace(PTREE, NOTREE)
        if f[1] < 0.05: p = p.replace("True pixel art", NOROAD + "True pixel art")
        return p
    add = ""
    if f[9] + f[10] > 0.004: add += PALIN + (GATE if gate else "") + (WOLDAE if gw else "")
    if f[8] > 0.03: add += TOWER
    if f[3] > 0.02: add += LAWN
    if f[11] > 0.003: add += TREE
    return M1.replace(KEY, add + KEY)
