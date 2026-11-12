# 쓴 프롬프트

이 문서에는 두 종류의 프롬프트가 있습니다.

1. **이미지 모델 프롬프트**: 양식 패스에서 창 270개마다 이미지 편집 모델(Qwen-Image-Edit-2511)에 넣은 영어 문장입니다. 공개된 그림을 만든 판을 원문 그대로 싣습니다. 코드로는 [`pipeline3d/gyeongbokgung/p3d_prompt.py`](../pipeline3d/gyeongbokgung/p3d_prompt.py)와 [`pipeline3d/yeouido/yd_prompt.py`](../pipeline3d/yeouido/yd_prompt.py)에 있습니다.
2. **Claude Code 에 한 지시**: 사람이 Claude Code(코딩 에이전트)에 입력한 문장 중 작업 방향을 바꾼 것들입니다. 말투·오타까지 그대로 옮겼습니다.

절차 전체는 [PIPELINE.md](PIPELINE.md), 안 됐던 것들은 [LESSONS.md](LESSONS.md)에 있습니다.

## 1. 이미지 모델 프롬프트

### 짜는 방식

- **바탕 문구 하나 + 창에 맞는 짧은 문장 몇 개.** 바탕 문구는 시험에서 통과한 것을 고치지 않고 씁니다. 창에 실제로 있는 것에 대한 문장만 바탕 문구의 고정 문장 앞에 끼웁니다. 고정 문장(`KEY`)은 `The pale ground stays plain quiet pavement` 입니다.
- **없는 것은 말하지 않습니다.** 창에 없는 것을 문장으로 말하면 모델이 그것을 지어냅니다. 문을 말하면 문을 짓고, 도로를 말하면 도로를 냅니다. 그래서 문장마다 0.5 m 분류 맵으로 "이 창에 그것이 있는가"를 먼저 셉니다.
- **부정 프롬프트는 없습니다.** CFG 1.0(Lightning 8스텝 LoRA)이라 부정 조건이 효과가 없습니다. 같은 조건을 양쪽에 넣었습니다. 금지는 긍정 프롬프트 안의 "no …, never …" 문장으로 합니다.
- **길게 새로 쓰지 않습니다.** 문구를 처음부터 길게 다시 쓴 판은 모델이 픽셀아트로 다시 그리지 않고, 3D 렌더 위에 소품만 얹었습니다. 여의도는 창당 끼우는 문장을 7개로 제한했습니다.

### 경복궁(공개판)

바탕 문구는 두 가지입니다. 궁 안 창은 `PAL`, 나머지 창은 `M1` 을 씁니다.

**`M1`** — 일반 동네. 소품 양을 세 단계로 시험한 뒤 고른 중간판입니다.

```text
Repaint this plain 3D render as finished, detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. Keep the exact camera, scale and layout: every building keeps its exact footprint, outline, height, roof shape and main wall and roof colour, and stays exactly where it is. Do not add, remove, merge or move any building. Dark charcoal ribbed roofs are hanok, traditional Korean houses: grey-black giwa tile roofs with crisp tile rows, ridge lines and slightly upturned eaves, wooden posts and paper lattice doors. Hanok roofs are plain unbroken tile: no skylights, no windows, no objects on them. Flat-roofed 2-5 storey buildings are Seoul villa houses and shop-houses; each looks a little different. Add a moderate amount of small everyday detail, calm and tidy, not crowded. Each flat rooftop stays mostly open and keeps its green or grey colour, with only two to four small things on it, chosen from: a water tank, a couple of planters, a few brown onggi jars, a short laundry line, one parasol with a table, a satellite dish, a cooling unit, a solar panel. Walls get brick courses, varied window frames, a few balconies, air conditioner units and drain pipes; some ground floors have a shop front with a plain awning and a blank signboard. The pale ground stays plain quiet pavement with faint paving lines; along the building edges place only an occasional potted plant, bench, parked bicycle, street lamp or utility pole. Do not turn the ground into asphalt roads. No letters, no numbers, no writing, no logos anywhere. No cars, no trucks, no vans, no motor vehicles of any kind, no people. True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look, no smooth 3D shading), limited muted palette, clean dithering, short crisp shadows, no blur, no gradients, no photographic texture, no UI.
```

**`PAL`** — 궁 안. 궁궐 시험 창에서 통과한 strict restyle 문구입니다.

```text
Repaint this plain 3D render as finished, richly detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. This is a strict restyle: keep the exact camera, scale and layout. Every hall, roof, stone platform, wall, path and lawn stays exactly where it is, with the same outline, size and colour. Do not add, remove, merge or move anything. Do not invent buildings or objects in empty areas. The buildings are Korean palace halls: sweeping dark charcoal giwa tile roofs with crisp tile rows, white plastered ridge lines and gently upturned eaves, red wooden columns and green lattice doors, green-and-red dancheong under the eaves, standing on pale grey granite platforms with steps. The long thin tiled strips are palace walls: low stone-and-brick walls with visible masonry courses, capped with a narrow dark tile roof; keep every wall continuous and exactly in place, never turn it into a hedge, a road or a path. Sand-coloured areas are packed-earth palace courtyards, paler strips are stone walkways, light green areas are mown lawn with subtle dithered texture. Green lumps are trees: draw each as a pixel-art tree crown on the same spot. True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look, no smooth 3D shading), limited muted palette, clean dithering, short crisp shadows, no blur, no gradients, no photographic texture, no text, no people, no vehicles, no UI.
```

**끼우는 문장**

| 이름 | 원문 |
|---|---|
| `PALIN` | `Buildings with dark tiled roofs, red columns and stone platforms are historic Korean palace halls and gates: keep them exactly as rendered and add nothing on or around them. Long thin tiled strips are palace walls: stone walls capped with a narrow dark tile roof, kept continuous and exactly in place.` |
| `GATE` | `The large gate is a fortress-style stone gate: a tall pale granite block base pierced by three arched passages with red doors, topped by a two-tier wooden pavilion with dark tile roofs. Keep the stone base, its three arches and both roof tiers exactly as rendered; it is not a wooden hall.` |
| `WOLDAE` | `In front of the gate lies a long raised pale stone-paved ceremonial platform with stone balustrades and steps: keep the platform stone-paved (not grass), with its balustrades, steps and the stone guardian statue exactly as rendered. Bright green areas are flat mown lawn: keep their exact shape.` |
| `TOWER` | `Tall blocks with bands of windows are office towers: keep each tower's wall colour (pale walls stay pale) and its window bands as rendered; do not recolour a tower dark.` |
| `LAWN` | `Bright green areas are flat mown lawn: keep them green and keep their exact shape.` |
| `TREE` | `Green lumps on trunks are trees: draw each as a pixel-art tree crown on the same spot, the same size.` |
| `NOTREE` | `There are no trees in this view: do not draw any trees or bushes.` |
| `NOROAD` | `Do not draw asphalt roads or lane markings on the pale ground.` |

**조립 규칙**(창 안 0.5 m 분류 비율 f[k], `prompt_for`)

| 조건 | 결과 |
|---|---|
| 궁궐·담·마당 > 3% 이고 일반 건물·한옥·타워 < 3%, 도로 < 10%, 바깥 지면 < 10% | `PAL` 을 쓴다 |
| ↳ 창이 광화문 문루 상자의 35% 이상을 덮음 | "The buildings are Korean palace halls:" 앞에 `GATE` 를 넣고 "The other buildings…"로 바꾼다 |
| ↳ 창이 월대 상자의 50% 이상을 덮음 | "Sand-coloured areas" 앞에 `WOLDAE` |
| ↳ 나무 < 0.2% | 나무 문장을 `NOTREE` 로 바꾼다 |
| ↳ 도로 < 5% | "True pixel art" 앞에 `NOROAD` |
| 그 밖 | `M1` 의 `KEY` 앞에 아래를 차례로 끼운다 |
| ↳ 궁궐 + 담 > 0.4% | `PALIN`(+ 문루·월대 조건이면 `GATE`, `WOLDAE`) |
| ↳ 타워 > 3% | `TOWER` |
| ↳ 잔디 > 2% | `LAWN` |
| ↳ 나무 > 0.3% | `TREE` |

270창 중 `PAL` 은 46창, 문루 문장은 2창에 들어갔습니다.

**조립된 예: 광화문 문루가 보이는 궁 안 창**(`PAL` + `GATE` + `NOROAD`, 1,832자)

```text
Repaint this plain 3D render as finished, richly detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. This is a strict restyle: keep the exact camera, scale and layout. Every hall, roof, stone platform, wall, path and lawn stays exactly where it is, with the same outline, size and colour. Do not add, remove, merge or move anything. Do not invent buildings or objects in empty areas. The large gate is a fortress-style stone gate: a tall pale granite block base pierced by three arched passages with red doors, topped by a two-tier wooden pavilion with dark tile roofs. Keep the stone base, its three arches and both roof tiers exactly as rendered; it is not a wooden hall. The other buildings are Korean palace halls: sweeping dark charcoal giwa tile roofs with crisp tile rows, white plastered ridge lines and gently upturned eaves, red wooden columns and green lattice doors, green-and-red dancheong under the eaves, standing on pale grey granite platforms with steps. The long thin tiled strips are palace walls: low stone-and-brick walls with visible masonry courses, capped with a narrow dark tile roof; keep every wall continuous and exactly in place, never turn it into a hedge, a road or a path. Sand-coloured areas are packed-earth palace courtyards, paler strips are stone walkways, light green areas are mown lawn with subtle dithered texture. Green lumps are trees: draw each as a pixel-art tree crown on the same spot. Do not draw asphalt roads or lane markings on the pale ground. True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look, no smooth 3D shading), limited muted palette, clean dithering, short crisp shadows, no blur, no gradients, no photographic texture, no text, no people, no vehicles, no UI.
```

### 여의도(공개판)

바탕은 경복궁의 `M1` 입니다. 여의도에는 한옥이 없으므로 한옥 두 문장(`Dark charcoal ribbed roofs are hanok …` 부터 `… no objects on them.` 까지)은 지웁니다. 고쳐 쓰지 않고 지우기만 합니다.

**건물 종류별 바탕(`base_for`).** 창 안 건물 화소를 저층·타워(타워형 랜드마크 포함)·아파트로 나눕니다. 타워 + 아파트가 12% 이상이면 `M1` 의 빌라·옥상·벽 세 문장을 지우고, 12% 이상인 종류의 문장으로 바꿉니다. 처음에는 모든 창에 `M1` 의 옥상 소품 문장이 들어가서 타워 옥상에 파라솔과 항아리가 올라갔습니다.

| 이름 | 원문 |
|---|---|
| `B_LOW` | `Low flat-roofed 2-5 storey buildings are shop-houses and small offices; each looks a little different. Their rooftops stay mostly open and keep their green or grey colour, with only two to four small things, chosen from: a water tank, a couple of planters, a few brown onggi jars, one parasol with a table, a satellite dish, a cooling unit, a solar panel. Their walls get brick courses, varied window frames, air conditioner units and drain pipes; some ground floors have a shop front with a plain awning and a blank signboard.` |
| `B_TOWER` | `Tall office towers are sleek modern high-rises: keep every tower roof exactly as rendered and add nothing to it. Tower walls are clean glass and panel grids from the ground to the top, never brick, with no balconies, awnings or air conditioner boxes; only the ground floor may have a glass lobby.` |
| `B_APT` | `Tall slab blocks with long rows of identical windows are apartment blocks: pale painted concrete walls with regular rows of windows and enclosed balconies, never brick; each apartment roof has only a small stair-and-lift box and a water tank, nothing else.` |

**랜드마크 문장.** 그 건물 화소의 35% 이상이 창 안에 있거나, 창 면적의 35% 이상을 그 건물이 차지할 때만 넣습니다. 뒤의 조건은 여의도에서 더했습니다. 1408 × 1024 창에는 화면 높이가 200 m 가까운 63빌딩이 35% 넘게 들어가지 않아서 앞 조건만으로는 끝내 걸리지 않았습니다. IFC 네 동 묶음은 15% / 10%, 파크원은 30% / 25% 입니다.

| 이름 | 원문 |
|---|---|
| `LM1` 국회의사당 | `The large pale stone hall with the teal-green dome is the National Assembly building, a monumental government hall, not an apartment or shop building: keep its pale grey granite walls, the ring of tall plain stone columns on every side, the flat blue roof deck with its pale stone rim around the green dome, the stone base and wide steps exactly as rendered. Its walls are pale stone with tall narrow windows, never brick; draw no shopfronts, awnings or signs on it and add nothing to its roof.` |
| `LM2` 63빌딩 | `The gold glass tower is the 63 Building: keep its smooth warm gold-bronze glass walls with a fine even grid on every face, the blue-grey lift strip running up its narrow end face, its dark bands and its outline exactly as rendered. It is the only gold building; its walls are gold glass from the ground to the top, never brick, never pale panels, never pink.` |
| `LM3` 파크원 | `The two tallest towers with thin red steel columns are Parc One: keep the pairs of red columns at both ends of each face running the full height, and the same blue-grey glass window bands on every floor (never brick, never white panels) exactly as rendered. Only these two towers have red columns: draw no red frames, red columns or red roof edges on any other tower or office block.` |
| `LM4` 더현대 서울 | `The low wide hall with eight red leaf-shaped truss masts along its long sides is a department store: keep its grey roof, the dark green roof-garden squares with small glass skylights and the red masts exactly as rendered. Its roof is grey and green, never white; add nothing on it.` |
| `LM5` IFC | `The pale silver-blue glass towers with slanted, faceted sides are IFC Seoul: keep their cut-crystal shapes, sloped pale-rimmed roof decks and smooth glass grid exactly as rendered; do not square them off.` |

**옥상 문장**은 그 건물의 꼭대기가 창 안에 있을 때만 넣습니다. 꼭대기가 없는 창에 옥상을 말하면 모델이 벽 중간에 지붕과 헬리패드를 지어냈습니다.

| 이름 | 원문 |
|---|---|
| `ROOF2` 63빌딩 | `The 63 Building's pale flat roof with the plain ring helipad stays exactly as rendered.` |
| `ROOF3` 파크원 | `Each Parc One tower ends in an eight-sided top with a beige rim band and a square grey helipad marked only by a white outline and a circle, no letters; keep it exactly as rendered.` |
| `CUT` | `Some tall towers continue past the top or bottom edge of this picture: there the same wall and the same window grid simply run on to the edge, unbroken, in one piece.` |

`CUT` 은 타워가 창의 위·아래 가장자리에 걸칠 때 넣습니다(가장자리 3줄에서 타워 화소 > 4%). 창 경계에서 타워가 반 토막 나고 그 위에 지붕이 얹히는 일을 막으려고 넣었습니다. 프롬프트만으로는 다 막지 못해서, 굽기의 랜드마크 벽 잠금이 마저 고칩니다.

**지형 문장**

| 이름 | 조건 | 원문 |
|---|---|---|
| `TOWER` | 타워 + 타워형 랜드마크 > 3% | 경복궁과 같음 |
| `BRIDGE` | 교량 > 1% | `The long straight grey strips crossing the water are road bridges: each deck is an empty asphalt road with lane markings and side railings only, on concrete piers. Never draw buildings, houses, shops, rooftops or any objects on a bridge; keep every deck, pier and railing exactly as rendered.` |
| `RIVER` | 강물 > 5% | `The wide blue area is the Han River: keep it open water with only small ripple marks; do not add boats, islands or bridges on it.` |
| `BANK` | 호안 > 0.4% 이고 물 > 2% | `The river edge is a stone embankment: keep its sloped stone band and concrete steps at the water exactly as rendered, no sand beach.` |
| `PARK` | 공원 잔디마당 > 2% | `Bright green open lawns in the park stay empty mown grass with nothing added on them; the trees stay exactly where they are.` |
| `LAWN` | 잔디 > 2%(`PARK` 가 없을 때) | 경복궁과 같음 |
| `TREE` | 나무 > 0.3% | 경복궁과 같음 |
| `KEEP` | 열린 면 > 35%, 또는 물이 넓고 건물이 적음, 또는 국회 창 | `Do not invent buildings or objects in empty areas.` |

문장이 7개를 넘으면 `LAWN`, `BANK`, `PARK`, `TREE`, `LM4`, `KEEP` 순서로 뺍니다. 270창에서 창당 문장 수는 1–6개였고, 가장 긴 프롬프트는 2,693자였습니다.

**조립된 예: 63빌딩이 보이는 창**(`LM2` `CUT` `TOWER` `PARK` `TREE`, 바탕은 `B_TOWER` + `B_APT`)

```text
Repaint this plain 3D render as finished, detailed isometric pixel art, like the hand-drawn map of a classic 16-bit city-building game. Keep the exact camera, scale and layout: every building keeps its exact footprint, outline, height, roof shape and main wall and roof colour, and stays exactly where it is. Do not add, remove, merge or move any building. Add a moderate amount of small everyday detail, calm and tidy, not crowded. Tall office towers are sleek modern high-rises: keep every tower roof exactly as rendered and add nothing to it. Tower walls are clean glass and panel grids from the ground to the top, never brick, with no balconies, awnings or air conditioner boxes; only the ground floor may have a glass lobby. Tall slab blocks with long rows of identical windows are apartment blocks: pale painted concrete walls with regular rows of windows and enclosed balconies, never brick; each apartment roof has only a small stair-and-lift box and a water tank, nothing else. The gold glass tower is the 63 Building: keep its smooth warm gold-bronze glass walls with a fine even grid on every face, the blue-grey lift strip running up its narrow end face, its dark bands and its outline exactly as rendered. It is the only gold building; its walls are gold glass from the ground to the top, never brick, never pale panels, never pink. Some tall towers continue past the top or bottom edge of this picture: there the same wall and the same window grid simply run on to the edge, unbroken, in one piece. Tall blocks with bands of windows are office towers: keep each tower's wall colour (pale walls stay pale) and its window bands as rendered; do not recolour a tower dark. Bright green open lawns in the park stay empty mown grass with nothing added on them; the trees stay exactly where they are. Green lumps on trunks are trees: draw each as a pixel-art tree crown on the same spot, the same size. The pale ground stays plain quiet pavement with faint paving lines; along the building edges place only an occasional potted plant, bench, parked bicycle, street lamp or utility pole. Do not turn the ground into asphalt roads. No letters, no numbers, no writing, no logos anywhere. No cars, no trucks, no vans, no motor vehicles of any kind, no people. True pixel art with visible square pixels and thin one-pixel dark outlines (no thick black comic outlines, no vector look, no smooth 3D shading), limited muted palette, clean dithering, short crisp shadows, no blur, no gradients, no photographic texture, no UI.
```

창별로 어떤 문장이 골라지는지는 `python yd_prompt_halfF.py` 로 표를 뽑아 볼 수 있고, `python yd_prompt_halfF.py X Y` 는 그 창의 전문을 찍습니다(분류 맵이 필요합니다).

### 판의 변화와 이유

**경복궁(시험 창 한두 장씩, 시드 11)**

| 판 | 바꾼 것 | 결과 |
|---|---|---|
| a | strict restyle(1,537자). 디노이즈 1.0 | 채택. 배치는 지켰지만 소품이 적었다 |
| b, c | 같은 문구에 조건 렌더를 시작 그림으로, 디노이즈 0.8 / 0.6 | 3D 렌더 느낌이 남아 버림 |
| r | 이전 그림을 두 번째 이미지로 주고 "양식만 가져와라" | 픽셀이 굵고 거칠어져 버림 |
| d1, d2 | "Where's Wally" 식으로 모든 면에 소품을 빼곡히 | 지나침. "no cars" 를 적었는데도 차를 그렸고, 한옥 지붕에 천창을 냈고, 빈 땅에 길을 냈다 |
| m1 / m2 | 소품 "적당히"(옥상당 2–4개 / 1–3개), 차·사람·글자 금지 문장을 따로, 한옥 지붕 금지 문장 | m1 채택. 위 세 문제 모두 0건 |
| g2 | 장소마다 문구를 처음부터 길게 다시 씀(도로 문장 포함) | 버림. 다시 그리지 않고 3D 렌더에 소품만 얹었고, 도로를 언급한 창에서 길을 지어냈다(월대가 도로가 됨) |
| r1(전 지도) | `M1` / `PAL` + 끼우는 문장 | 문이 안 보이는 이웃 창에도 문 문장이 들어가 문을 여러 채 지어냈다. 큰길이 많은 창에 `PAL` 을 쓰니 전각을 지어냈다 |
| r3(공개판) | 문루·월대 문장은 상자를 35% / 50% 이상 덮는 창에만. `PAL` 조건에 도로 < 10%, 바깥 지면 < 10% 추가. 시드 213 | 채택 |

**여의도(창 2 × 2 시험 블록: 국회·63·업무지구·강)**

| 판 | 바꾼 것 | 왜 |
|---|---|---|
| v5 | `M1` 에서 한옥 문장만 빼고, 국회·63·파크원 문장과 강·교량·호안·공원 문장을 끼움. 63 은 "curved tapering outline" | 경복궁 방식을 그대로 옮김 |
| v6 | 63 문장을 "rose-gold glass … fine even grid, lift strip, dark bands"로 다시 씀. 파크원 "pairs of red columns … never white panels", 다른 타워에 붉은 기둥 금지. 더현대(`LM4`)·IFC(`LM5`) 추가. 묶음 문턱, 문장 수 상한 6, 국회 창에는 항상 `KEEP` | 63 모델을 사진대로 고쳤다(곡선 방향). 시험에서 파크원의 붉은 틀이 이웃 타워로 번졌다. 긴 프롬프트는 소품만 얹었다 |
| v7 | 건물 종류별 바탕(`B_LOW` `B_TOWER` `B_APT`). 처음 `B_TOWER` 는 "roof carries only building machinery, chosen from: … a round helipad mark …" | 타워 옥상에 파라솔·항아리가 올라감. 사용자 지시 "건물 속성에 따라 좀 다르게" |
| halfF(공개판) | 판 F(12.5 cm) 좌표로 감싼 모듈. `B_TOWER` 를 "keep every tower roof exactly as rendered and add nothing" 으로. 옥상 문장 `ROOF2` `ROOF3` 는 꼭대기가 창 안일 때만. `CUT` 추가. 63 "gold-bronze … never pink", 더현대 "grey roof … never white". 파크원 문턱 30% / 25%, 상한 7 | 옥상을 Blender 에서 모델링하고 굽기에서 조건 렌더로 잠그게 되어, 프롬프트는 "그린 대로 두라"만 하면 됐다. "chosen from …" 은 이미 그려진 헬리패드 위에 또 얹으라는 말이 됐다. 시험에서 63 이 분홍으로 칠해졌고, 더현대 모델이 바뀌었다 |

### 안 된 문장의 예

| 문장(원문) | 무엇이 됐나 |
|---|---|
| `… crossed with a busy 'Where's Wally' search-and-find illustration. … Now pack every surface with small charming everyday details, densely, so there is something to discover everywhere.` | 지나치게 빼곡해졌고, 소품 목록에 있던 천창(`skylights`)을 한옥 지붕에도 냈다 |
| `Alleys and ground: … parked bicycles and scooters, stacked crates, fruit stalls …` + `… no people, no cars, no UI.` | 끝에 "no cars" 가 있는데도 차를 그렸다. 금지를 문장 하나로 따로 떼자(`No cars, no trucks, no vans, no motor vehicles of any kind, no people.`) 없어졌다 |
| `Dark grey bands are asphalt streets and narrow alleys: keep their exact position and width, paint dark asphalt with the white lane dashes and zebra crossings that are already there. Do not widen them and do not add new roads.` | "더하지 말라"고 했는데도 길을 지어냈다. 도로를 말하지 않는 쪽(`Do not turn the ground into asphalt roads.`)이 나았다 |
| `The gold glass tower is the 63 Building: keep its golden glass walls, curved tapering outline and fine vertical lines exactly as rendered.` | 장면의 63 모델이 "위로 좁아지는 볼록 곡선"으로 잘못 만들어졌을 때, 그 형태를 그대로 지키라고 한 문장이다. 사진대로 모델을 고친 뒤 문장도 함께 고쳐야 했다 |
| `… each tower roof carries only building machinery, chosen from: a low grey mechanical penthouse, a row of cooling units, a round helipad mark, a thin antenna mast.` | 이미 모델링된 헬리패드·기계실 위에 또 얹었다 |
| `The low white hall with leaning red masts is a department store: keep its white roof, long glass skylight and red masts exactly as rendered.` | 기억에 의존한 형태(흰 지붕) 문장이다. 더현대 모델을 회색·녹색 지붕과 잎 모양 트러스로 고친 뒤 문장도 고쳤다. 장면을 바꾸면 그 건물 문장을 같이 확인해야 한다 |

## 2. Claude Code 에 한 지시

작업 기록(세션 로그)에서 사람이 직접 입력한 짧은 지시만 골랐습니다. 도구 출력·시스템 메시지·작업 분배 알림은 뺐고, 개인 정보·장비 이름·경로가 들어간 문장도 뺐습니다. 시각은 한국 시간입니다. 11-10 의 네 개는 2D 판 때의 지시이고, 나머지가 지금 방식으로 넘어오는 과정입니다.

| 시각 | 지시(원문) | 맥락 |
|---|---|---|
| 11-10 09:18 | 나는 인상적인 트위터에 바이럴 될 웹페이지를 만드는게 목표야 상황 파악하고 진행해줘 | 목표 설정. 이후 모든 판단(첫 화면, 공유 미리보기, 용량)의 기준 |
| 11-10 13:46 | 응 이거 특히 트위터 인앱브라우저에서 잘 열려야하고 거기서 보기 좋은 레이아웃이어야해 염두애둬줘 | 모바일 인앱 브라우저를 1순위 환경으로 |
| 11-10 14:44 | 야간은 좀 더 광원 중심으로 주변부가 밝아지는 효과를 개선해야될 필요가 있겠네  지금은 딱 광원만 보이는데 약간 그 현대의 jrpg에서 쓰는 그런 느낌을 활용하면 좋겠어 | 밤 조명을 점광원에서 주변 번짐(bloom)으로 |
| 11-10 22:28 | 밤이 이렇게 점묘화처럼 나오는건 왜일까 | 밤 창문이 모래알처럼 보이는 문제 제기 → 창문 격자 방식으로([LESSONS.md](LESSONS.md)) |
| 11-11 05:42 | 이거 그냥 다시 전체적으로 깔끔하게 재생성 하는건 어때? | 2D 판의 땜질을 그만두고 다시 만들기로 |
| 11-11 05:44 | 응 이거 전채 기준 디노이즈 하지 말고 밑그림으로 부터 고해상도로 만드는데 낫지 싶은데 | 이전 그림을 고치는 대신 밑그림에서 새로 그리기(디노이즈 1.0) |
| 11-11 08:26 | 어떻게 하는게 좋을까? 새로 그려지는것 괜찮아. 랜드마크들 최대한 확보해서 유지만 되면 그외 건물들 디테일은 크게 중요하지 않아 그저 원경과 근경이 각각 다 충분히 흥미로우면 괜찮아 | 우선순위: 랜드마크 고증 > 일반 건물 |
| 11-11 08:28 | 랜드마크 지금 그림을 유지할 필요도 없어 스타일 좋게 다시뽑아도 좋지. 이름난 랜드마크가 아니더라도 좋으니 건물사진들 최대한 확보해서 활용해보자 | 사진을 보고 모델링하는 방식의 시작 |
| 11-11 09:45 | 괜찮네. 디테일은 이미지모델이 채우게 하면 되지 않을까? 나는 월리를 찾아라 같은 느낌으로 디테일이 빼곡하면 재밌을것 같아서, 궁궐과 랜드마크들은 최대한 고증을 지키는게 맞고 그 외에는 말이야 | 3D 장면은 뼈대, 세부는 모델이 → 빼곡판(d1) 시험 |
| 11-11 09:50 | 지금은 그런데 또 너무 과하긴 하다 ㅎㅎ 적당히 해줘. 너무 오바다 | 중간판(m1)으로 |
| 11-11 09:54 | 이정도면 괜찮은것 같아. 이제부터 전체 지도를 높은 품질로 구현해줘 | m1 승인, 전 지도 270창 실행 |
| 11-11 13:06 | 세개를 하나에 넣기는 힘든가? 그럼 어의도만 한번 해볼까 빌딩들이 있는곳도 좀 그려보고 싶거든 강과 빌딩 | 두 번째 지도로 여의도 |
| 11-11 14:06 | 여의도에 랜드마크인 국회의사당 같은 부분이 안드러나잇네. 여의도 공원도 좀더 디벨롭 해야되고 한강주변 공원도 그렇고 랜드마크들 더 디테일해야해 | 랜드마크 전용 모델과 공원 규칙 |
| 기록 없음 | 모서리 곡면이 문제가 아니라 수직선이 곡선이잖아. 건물 사진들 좀 참고 | 63빌딩 곡선 방향 교정(작업 메모에 남은 문장) |
| 11-11 20:05 | 응 이거 건물 속성에 따라 좀 다르게 구성해야겠네 | 건물 종류별 프롬프트(`B_LOW` `B_TOWER` `B_APT`)와 옥상 소품 |
| 11-11 20:08 | 이런거 보면 참고가 충분히 될텐데 헬리포트 같은거 위성뷰나 항공뷰 좀 쓰라그러자 랜드마크는 | 옥상은 위성·항공 사진을 보고 |
| 11-11 21:22 | 내 생각엔 헬리포드나 옥상표현을 최대흔 블랜더로 랜다 해서 넘기는게 낫지 않았나 싶네 | 옥상을 Blender 로 그리고 굽기에서 잠금(지붕 잠금) |
| 11-12 02:18 | 응 먼저 배포하고 마저 품질개선 해줘 | 여의도 공개 후 다듬기 |
| 11-12 07:50 | 사람이 너무 적다 여의도에 공원에도 사람이 있어야 하고 여기저기 그 경복궁에서 넣었던것처럼 디테일좀 개선해보자 힌강공원엔 자전거도 다니면 좋겠고 전반적으로 자동차도 훨씬 많아야하고 | 여의도의 사람·자전거·차(진행 중, [APP.md](APP.md)) |

"Blender 로 최대한 자세하게 세운다"는 큰 방향은 선택지 답으로 정해져서 입력 문장으로는 남아 있지 않습니다.

### 일을 나눈 방식

사람 한 명이 Claude Code 세션 하나(리드)와 대화하고, 리드가 일을 쪼개 다른 Claude Code 세션(워커)에 지시서로 넘겼습니다. 워커끼리는 직접 말하지 않고, 결과는 노트 파일과 완료 보고로 리드에게 돌아옵니다.

| 역할 | 맡은 일 |
|---|---|
| 리드 | 사람과 대화, 판정(그림을 보고 채택·폐기), 양식 패스 실행, 지시서 작성, 공개 |
| 장면 워커 | 여의도 장면 자료·카메라 판·조건 렌더, 분류 맵 |
| 랜드마크 워커 | 사진을 찾아 보고 랜드마크 모델·툰 재질 |
| 굽기 워커 | 잠금·양자화·타일, 시험 구역 시트 |
| 앱 워커 | 뷰어(지도 전환, 차·사람, 밤 창문, Safari 대응) |
| 그 밖 | 이음매 시험, 국가유산청 모델 정합, 사진 수집 |

지시서는 늘 같은 꼴이었습니다: **배경**(무엇이 바뀌었고 왜) → **할 일**(번호 목록, 산출물 경로) → **검증**(숫자로 확인할 것) → **제약**(GPU 금지, 원본 폴더 수정 금지, 커밋·배포 금지, CPU 프로세스 수 상한) → **끝나면** 완료 보고.

예: 여의도 9차 지시서의 요지.

- 배경: 랜드마크 워커가 옥상 면 안쪽만 고쳤다. 윤곽·벽·높이·ID 는 그대로라고 창 4곳에서 확인했고, 전체 판은 아직 확인하지 않았다.
- 주의: 지금 리드의 전체 양식 패스가 현재 조건 렌더 폴더를 읽는 중이니 그 폴더는 건드리지 말 것.
- 할 일:
  1. 타일 24장을 다시 렌더해 복사본 폴더에 이어 붙인다(CPU 16개 이하).
  2. 새 ID 패스와 옛 ID 패스의 다른 화소 수를 전체 판에서 센다. 0이 아니면 어디가 왜 다른지 보고한다(옥상 설비 상자가 새 ID 로 생긴 정도는 괜찮다).
  3. 굽기가 양식 결과는 옛 판, 지붕 잠금의 조건 렌더는 새 판을 쓰도록 명령 한 줄을 정리한다. 시험 그림 세 장에 적용한 전·후를 남긴다.
- 끝나면: 리드에게 알리고 완료 보고.

양식 패스가 GPU 를 쓰는 동안 렌더·굽기는 CPU 로 나란히 돌릴 수 있었습니다. 대부분의 시간 절약은 이렇게 나눈 데서 나왔습니다.
