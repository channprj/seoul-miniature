#!/bin/bash
# OSM(Overpass) 자료 받기. 요청에는 개인·프로젝트 식별 정보를 넣지 않는다(User-Agent 는 일반 이름).
# 사용: ./fetch_osm.sh   → osm/{buildings,roads,areas,points}.json   (ODbL, © OpenStreetMap contributors)
cd "$(dirname "$0")/osm" || exit 1
BB="37.503,126.897,37.552,126.960"   # 남,서,북,동
EP="${OVERPASS:-https://overpass-api.de/api/interpreter}"
q() { # 이름, 질의
  [ -s "$1.json" ] && { echo "skip $1"; return 0; }
  curl -sS --fail --max-time 600 -A "osm-area-fetch/1.0" --data-urlencode "data=[out:json][timeout:300][bbox:$BB];$2" "$EP" -o "$1.json.part" && mv "$1.json.part" "$1.json" && echo "ok $1 $(wc -c < $1.json)" || { echo "FAIL $1"; return 1; }
  sleep 5
}
q buildings '(way["building"];relation["building"];way["building:part"];relation["building:part"];);out tags geom;' || exit 1
q roads '(way["highway"];way["railway"];way["man_made"="bridge"];relation["man_made"="bridge"];way["bridge:support"];);out tags geom;' || exit 1
q areas '(way["natural"];relation["natural"];way["waterway"];relation["waterway"];way["water"];relation["water"];way["leisure"];relation["leisure"];way["landuse"];relation["landuse"];way["amenity"="parking"];way["man_made"~"pier|embankment|breakwater"];way["barrier"];);out tags geom;' || exit 1
q points '(node["natural"="tree"];node["highway"~"crossing|traffic_signals"];);out;' || exit 1
# 관계(멀티폴리곤)는 멤버 형상이 필요하다(out tags geom 은 멤버를 빼므로 따로 받는다)
q rel_buildings '(relation["building"];relation["building:part"];);out geom;' || exit 1
q rel_areas '(relation["natural"];relation["water"];relation["leisure"];relation["landuse"];relation["man_made"="bridge"];);out geom;' || exit 1
