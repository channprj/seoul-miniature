#!/bin/bash
# 테헤란로 일대 OSM(Overpass) 자료 받기. 요청에는 개인·프로젝트 식별 정보를 넣지 않는다(User-Agent 는 일반 이름).
# 사용(작업 폴더에서): bash fetch_osm.sh   → osm/{buildings,roads,areas,points,rel_buildings,rel_areas}.json   (ODbL, © OpenStreetMap contributors)
# 여의도 것과 다른 점: 건물이 많아 한 번에 받으면 서버가 끊는다(502/504) → 아홉 칸으로 나눠 받아 합친다. 역 출입구·사적·보행 광장을 더 받는다.
# Overpass 가 계속 502/504 를 내면 같은 범위를 https://api.openstreetmap.org/api/0.6/map?bbox=서,남,동,북 로 받아(한 번에 노드 5만 개까지) 같은 꼴(elements[].geometry)로 바꿔 써도 된다.
# 공개판의 남쪽 띠(위도 37.477–37.486)는 그렇게 받았다.
mkdir -p osm && cd osm || exit 1
BB="37.477,127.014,37.531,127.076"   # 남,서,북,동. 판 T 의 네 귀퉁이(위도 37.483–37.526)와 판 아래쪽 밖의 높은 건물까지 덮는다
EPS="${OVERPASS:-https://overpass-api.de/api/interpreter https://overpass.private.coffee/api/interpreter}"
q() { # 이름, 상자, 질의
  [ -s "$1.json" ] && { echo "skip $1"; return 0; }
  for try in 1 2 3 4; do for EP in $EPS; do
    curl -sS --fail --max-time 600 -A "osm-area-fetch/1.0" --data-urlencode "data=[out:json][timeout:300][bbox:$2];$3" "$EP" -o "$1.json.part" 2>/dev/null && mv "$1.json.part" "$1.json" && echo "ok $1 $(wc -c < $1.json)" && sleep 5 && return 0
    sleep 10; done; done
  echo "FAIL $1"; return 1
}
i=0
for B in "37.477,127.014,37.495,127.035" "37.477,127.035,37.495,127.056" "37.477,127.056,37.495,127.076" "37.495,127.014,37.513,127.035" "37.495,127.035,37.513,127.056" "37.495,127.056,37.513,127.076" \
         "37.513,127.014,37.531,127.035" "37.513,127.035,37.531,127.056" "37.513,127.056,37.531,127.076"; do
  i=$((i+1)); q b$i "$B" '(way["building"];way["building:part"];);out tags geom;' || exit 1
done
python3 -c "
import json; seen = {}
for i in range(1, 10):
    for e in json.load(open(f'b{i}.json'))['elements']: seen[(e['type'], e['id'])] = e
json.dump({'elements': list(seen.values())}, open('buildings.json', 'w')); print('buildings', len(seen))"
q roads "$BB" '(way["highway"];way["railway"];way["man_made"="bridge"];relation["man_made"="bridge"];way["bridge:support"];);out tags geom;' || exit 1
q areas "$BB" '(way["natural"];relation["natural"];way["waterway"];relation["waterway"];way["water"];relation["water"];way["leisure"];relation["leisure"];way["landuse"];relation["landuse"];way["amenity"="parking"];way["man_made"~"pier|embankment|breakwater"];way["barrier"];way["historic"];relation["historic"];way["tourism"];way["highway"="pedestrian"]["area"="yes"];);out tags geom;' || exit 1
q points "$BB" '(node["natural"="tree"];node["highway"~"crossing|traffic_signals"];node["railway"~"subway_entrance|station"];node["station"="subway"];node["historic"];node["tourism"];);out;' || exit 1
q rel_buildings "$BB" '(relation["building"];relation["building:part"];);out geom;' || exit 1
q rel_areas "$BB" '(relation["natural"];relation["water"];relation["leisure"];relation["landuse"];relation["man_made"="bridge"];relation["historic"];);out geom;' || exit 1
# OSM 에 건물이 비어 있는 블록을 채울 풋프린트(Overture 건물 테마; prep_extra.py 가 비 OSM 출처만 쓴다). 없어도 된다.
[ -s overture_buildings.geojson ] || uvx overturemaps download --bbox=127.014,37.477,127.076,37.531 -f geojson --type=building -o overture_buildings.geojson || echo "overture 건너뜀"
