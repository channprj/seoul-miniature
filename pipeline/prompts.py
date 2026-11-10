#!/usr/bin/env python3
"""타일에 실제로 들어 있는 클래스만 언급하는 프롬프트를 만든다(없는 것을 지어내지 않게)."""
import numpy as np

HEAD = ("Repaint this flat-colour block-out as finished, richly detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. "
        "This is a strict repaint: keep the exact camera, scale and layout. Every shape stays exactly where it is, with the same outline and size. "
        "Do not add, remove, merge or move any building, road, path, lawn, tree or water. Do not invent new objects in empty areas. ")
TAIL = ("True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look), limited muted palette, clean dithering, short soft shadows falling to the lower right, "
        "no blur, no gradients, no photographic texture, no text, no people, no vehicles, no UI.")
PARTS = {
    'road': "Dark grey bands with white dashed lines are asphalt roads: paint them dark grey asphalt with white lane markings and a few zebra crossings, keep their exact width. Roads are never water, never blue. ",
    'noroad': "There are no roads and no cars anywhere in this image. ",
    'ground': "Pale beige areas are plain flat pavement: keep them plain and quiet, with only faint paving-slab lines. ",
    'lawn': "Light green areas are mown lawn with subtle dithered grass texture. ",
    'tree': "Dark green lumps are trees: draw each as a pixel-art tree crown (pine, zelkova, ginkgo or willow) with highlights, on the same spot. ",
    'water': "Blue areas are water with stone edging and small pixel ripples; keep the exact shoreline, add no islands. ",
    'court': "Sand-coloured areas are the palace's packed-earth courtyards; slightly darker beige strips are stone walkways. ",
    'palace': ("Striped slate-blue shapes with dark red walls are traditional Korean palace architecture (the stripes mark roof tiles; paint these roofs dark charcoal grey). Larger ones are halls: sweeping dark-grey giwa tile roofs with visible tile rows, "
               "ridge lines and gently upturned eaves, red wooden columns and lattice doors, green-and-red dancheong under the eaves, grey stone platforms. "
               "Long thin striped strips are the tiled roofs of palace walls and roofed corridors: draw them as low red walls capped with a narrow dark tile roof, never as roads. "),
    'k1': ("Small 2-5 storey buildings with red-brown brick or pale tiled walls are Seoul multi-family 'villa' houses and shop-houses: keep each one's wall and roof colour from the block-out. "
           "Rooftops painted green or grey with yellow and blue water tanks, satellite dishes, stair penthouses, potted plants and laundry lines; outside stairs, balconies, small ground-floor shops with coloured awnings and signboards. Every building looks a little different. "),
    'k2': ("Charcoal striped roofs on off-white walls are hanok, traditional Korean houses: curved grey-black giwa tile roofs with visible tile rows and ridge lines, wooden doors and lattice windows, small inner courtyards, low stone-and-tile walls, narrow alleys between them. "),
    'k3': ("Mid-rise blocks are commercial and office buildings: stone, tile or brick facades with regular window bands, ground-floor shops, rooftop cooling units and signs. "),
    'k4': ("Tall blue-glass or dark blocks are modern office towers: curtain-wall glass grids, crisp vertical mullions, rooftop mechanical floors and helipads, glazed lobbies at street level. "),
    'k5': ("Tall pale slabs are Korean apartment blocks: rows of balconies and windows, a painted accent stripe, flat roofs with lift huts. "),
    'k6': ("Buildings with green, copper or terracotta roofs are public buildings such as schools, museums, galleries and churches: larger windows, entrances with steps, courtyards. "),
    'k7': ("Bright blue striped roofs on white walls are the Blue House compound: traditional hipped roofs of blue glazed tiles, white walls, wooden columns. "),
}

def prompt_for(cls_tile, kind_tile=None):
    """cls_tile: 클래스 맵의 타일 영역, kind_tile: 건물 성격 맵의 같은 영역(없으면 빌라로 본다)."""
    n = cls_tile.size
    f = {k: float((cls_tile == k).sum()) / n for k in range(12)}
    p = HEAD
    p += PARTS['road'] if f[2] > 0.004 else PARTS['noroad']
    if f[8] + f[9] > 0.004: p += PARTS['palace']
    if f[5] > 0.01: p += PARTS['court']
    if f[6] + f[7] > 0.004:
        p += "Buildings keep exactly the footprint, height, roof colour and wall colour of the block-out. "
        if kind_tile is None:
            p += PARTS['k1']
        else:
            for k in range(1, 8):
                if float((kind_tile == k).sum()) / n > (0.002 if k in (2, 7) else 0.01): p += PARTS['k%d' % k]
    if f[1] + f[11] > 0.03: p += PARTS['ground']
    if f[3] > 0.01: p += PARTS['lawn']
    if f[10] > 0.004: p += PARTS['tree']
    if f[4] > 0.002: p += PARTS['water']
    if f[0] > 0.02: p += "The flat pale blue-grey area is empty background outside the map: leave it as one flat colour, paint nothing there. "
    return p + TAIL
