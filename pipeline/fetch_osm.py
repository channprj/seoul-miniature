#!/usr/bin/env python3
"""밑그림용 OSM 데이터를 Overpass 에서 받는다(© OpenStreetMap contributors, ODbL).

범위는 캔버스(fit_rect + 여유)를 덮는 경위도 상자. 결과는 gitignore 된 경로에 저장한다.
사용: python3 pipeline/fetch_osm.py <out.json>
"""
import json
import sys
import urllib.parse
import urllib.request

W, S, E, N = 126.966, 37.569, 126.988, 37.589
B = f"{S},{W},{N},{E}"
Q = f"""
[out:json][timeout:120];
(
  way["building"]({B});
  relation["building"]({B});
  way["highway"]({B});
  way["waterway"]({B});
  way["natural"="water"]({B});
  relation["natural"="water"]({B});
  way["leisure"~"park|garden|pitch|playground"]({B});
  way["landuse"~"grass|forest|recreation_ground|meadow|village_green"]({B});
  way["natural"~"wood|scrub|grassland"]({B});
  relation["natural"="wood"]({B});
  relation["landuse"="forest"]({B});
  relation(5501517);
);
out geom;
"""
req = urllib.request.Request(
    "https://overpass-api.de/api/interpreter",
    data=urllib.parse.urlencode({"data": Q}).encode(),
    headers={"User-Agent": "osm-guide-fetch/0.1"},
)
with urllib.request.urlopen(req, timeout=180) as r:
    data = json.load(r)
out = sys.argv[1]
json.dump(data, open(out, "w"))
print("elements", len(data["elements"]), "->", out)
