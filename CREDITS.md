# 출처와 라이선스

2026-11-11 기준. 개인 비상업 연구 프로젝트다. 아래 표의 "확인"은 그날 각 페이지를 직접 읽어 확인한 내용이다.

## 이 프로젝트가 만든 것의 라이선스

2026-11-12 결정. 다른 사람이 가져다 새 콘텐츠를 만들 수 있게 열어 둔다. 용도별 안내와 그대로 복사해 쓰는 출처 문구는 [docs/REUSE.md](docs/REUSE.md).

| 무엇 | 라이선스 | 저작자 표시 |
|---|---|---|
| 그림: 배경 그림·타일·`og.png`·보조 맵 PNG(깊이·분류·수관·아틀라스), 이 사이트를 찍은 영상·스크린샷 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 「서울 미니어처 by midagedev, CC BY 4.0」 + 아래 원천 표시 |
| 장면 데이터(`scene.json`, `map.json`, `winfaces.json`), 3D 장면 `.blend`·`.glb`와 여의도 랜드마크 `.glb`(GitHub Releases) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) | 「© OpenStreetMap contributors」 + 아래 원천 표시 |
| 코드·문서 | MIT(`LICENSE`) | 저작권 표시와 허락 문구 |
| 배경음 | 이번 결정에 넣지 않았다 | 아래 「배경음 생성 모델」 |

- 그림은 아래 원천으로 만든 3D 장면의 렌더를 다시 그린 것이라, 원천의 표시 조건(OSM, 공공누리, CC BY)이 그림을 쓸 때도 따라온다. 그래서 이 프로젝트 표시와 원천 표시를 함께 요구한다.
- 이 표의 라이선스는 이 프로젝트가 만든 부분에 대한 것이다. 그림 속 실제 건물의 생김새(건축저작물·상표·디자인)에 대한 권리는 따로 있을 수 있다(docs/REUSE.md 「주의」).

## 브라우저로 나가는 것

| 파일 | 내용 | 어디서 왔나 |
|---|---|---|
| `redraw/bg.png`, `redraw/bg_1x.png`, `redraw/tiles/` | 배경 그림(5504×3392 = 0.25 m/px, 저사양용 2752×1696)과 확대용 타일(가장 세밀한 단계 22016×13568 = 6.25 cm/px) | 아래 데이터로 만든 3D 장면을 렌더하고, 그 렌더를 Qwen-Image-Edit-2511 로 양식만 바꿔 다시 그린 뒤 128색으로 정리 |
| `redraw/depth_rg8.png` | 가림 판정용 깊이 | 같은 3D 장면의 렌더 깊이 |
| `redraw/classes.png`, `redraw/crown.png` | 픽셀별 종류(도로·잔디·지붕 등), 나무 수관 마스크 | 같은 3D 장면의 ID 렌더 + OSM |
| `web-poc/occlusion_class8.png` | 검증 도구용 가림 판정 오버레이 | 같은 3D 장면 |
| `web-poc/scene.json.gz` | 카메라, 차선, 보행 경로 | OSM 도로 + 직접 작성. 도로 형상은 OSM 에서 온 데이터라 이 파일은 **ODbL 1.0** 으로 제공한다 |
| 사람·차·불빛·날씨 | 코드(`src/movers.js`, `src/vehicles.js`, `src/render.js`) | 직접 작성 |
| `audio/bgm.mp3`, `audio/bgm_night.mp3` | 배경음(루프, 기본 꺼짐) | ACE-Step 1.5 로 생성. 아래 "배경음 생성 모델" |

사진과 게임 에셋은 들어가지 않는다.

## 데이터 원천과 조건

| 원천 | 라이선스 (확인) | 요구 사항 | 이 앱의 표시 |
|---|---|---|---|
| OpenStreetMap | ODbL 1.0 | "© OpenStreetMap contributors" 표시 + ODbL 로 제공됨을 밝힘 + openstreetmap.org/copyright 링크 | 화면 하단 상시 표시 + 패널 |
| Overture Maps 건물 테마 | ODbL (테마 단위), 일부 원천 CC BY 4.0 | "Overture Maps Foundation, overturemaps.org" | 패널 |
| East Asian Buildings (Qian Shi 외 2023, doi:10.5281/zenodo.8174931) | CC BY 4.0 | 저작자 표시 | 패널 |
| GIS건물통합정보 (국토교통부, data.go.kr/data/15083092) | 공공누리 제1유형 | 출처 표시(기관·저작물명·URL), 가능하면 링크, 기관이 후원한 것처럼 보이게 하지 말 것 | 패널(공공누리 예시 문구 형식) |
| 사적 경복궁 광화문, 광화문 월대 일원 3D 기록 (국가유산청, 2023, digital.khs.go.kr) | 공공누리 제1유형 | 위와 같음 | 패널 + 화면 하단 상시 표시 |
| 경복궁 전각 3D 기록 46건 (국가유산청 디지털 서비스, digital.khs.go.kr). 아래 "국가유산청 전각 목록" | 공공누리 제1유형. 46건 모두 2026-11-11 자료 페이지에서 유형 표시를 확인 | 위와 같음 | 패널 + 화면 하단 상시 표시 |

- 공공누리 제1유형은 상업 이용과 2차적 저작물 작성을 모두 허용한다(출처 표시 조건).
- ODbL 의 동일조건은 "파생 데이터베이스"에 붙는다. 그림과 깊이 이미지는 OSMF FAQ 기준으로 Produced Work 이고, 여기서는 OSM 데이터를 고쳐서 재배포하지 않는다. 이 해석은 OSMF 의 설명이며 법률 자문이 아니다.
- V-World 건물 정보는 Hugging Face `serene9/daesang-tiles`(2026-09-09 스냅샷, 카드 표기 CC BY 4.0)를 거쳐 받았다. 원 저작물 조건(공공누리 1유형)을 따른다.
- 국가유산청 원본 모델(FBX·텍스처)과 그것을 변환한 3D 파일은 레포에도 배포물에도 없다. 전각 모델은 3D 장면에 배치해 색·깊이를 렌더하는 데만 썼고, 배포되는 것은 그 렌더를 AI 로 다시 그린 2D 그림과 깊이 이미지다. GitHub Releases 의 경복궁 `.blend`·`.glb` 에도 국가유산청 모델은 없다. 전각 자리(46건 + 광화문)에는 OSM 윤곽과 높이로 만든 대체 모형이 서 있고, 자리 표시(컬렉션 `KHS_SLOTS`)와 직접 받은 모델을 끼우는 스크립트(`pipeline3d/gyeongbokgung/insert_khs.py`)를 함께 낸다.

### 국가유산청 전각 목록

본 저작물은 '국가유산청'에서 작성하여 공공누리 제1유형으로 개방한 '경복궁 3D 기록'을 이용하였으며, 해당 저작물은 '국가유산청 디지털 서비스, [digital.khs.go.kr](https://digital.khs.go.kr)'에서 무료로 다운받으실 수 있습니다.

경회루(섬 포함), 수정전, 강녕전 일원(함원전·흠경각), 건춘문, 영추문, 신무문, 광화문 일원(동·서 수문장청, 용성문, 협생문, 초관처소, 군사방), 흥례문 일원(흥례문, 유화문, 기별청, 행각), 동궁(계조당·비현각·자선당·통장청), 건청궁(곤녕합·장안당·초양문·복수당·행각), 태원전 일원(태원전, 건숙문, 경안문, 숙문당, 복도, 동측·북측 세답방), 함화당·집경당, 흥복전, 자경전 일원(자경전, 청연루, 협경당, 복안당, 행각), 소주방(내소주방·외소주방·복회당·제수합).

이 46건의 형태를 3D 장면에 넣었다. 목록에 없는 전각은 OSM 윤곽과 높이로 만든 모형이다.

## 테헤란로 (`assets/teheran/`)

이 포크에서 더한 지도다. 그림은 Blender 장면의 렌더를 색만 줄인 것이고, 이미지 생성·편집 모델을 쓰지 않았다.

| 자료 | 쓴 곳 | 조건 |
|---|---|---|
| OpenStreetMap: 건물 윤곽·높이·층수, 도로, 녹지, 공사 터(`landuse=construction`), 왕릉(`historic=tomb`), 지하철 출입구·역 | 배치 전부 | ODbL 1.0, 「© OpenStreetMap contributors」 |
| Overture Maps 건물 테마 가운데 OSM 이 아닌 출처의 풋프린트(East Asian Buildings, doi:10.5281/zenodo.8174931) 1,429개 | OSM 에 건물이 비어 있는 블록의 건물 윤곽(높이는 면적으로 추정) | CC BY 4.0 (Overture 배포본: CDLA-Permissive-2.0 / ODbL) |

- 랜드마크의 색·입면 구성은 네이버 지도 거리뷰를 사람이(작업한 에이전트가) 눈으로 보고 3D 모델에 옮겼다. 화면을 저장소나 그림에 넣지 않았고, 확인용으로 찍은 화면은 작업 폴더 밖 임시 폴더에만 두었다.
- 건물 높이는 OSM `height` → `building:levels` 순으로 읽고, 없으면 건물 종류·면적·큰길 접함으로 추정했다. 봉분 언덕의 높이, 공사 현장의 골조·장비 배치는 연출이다.
- 장면 데이터(`map.json`)는 OSM 에서 왔으므로 **ODbL 1.0**, 그림은 다른 지도와 같이 **CC BY 4.0** 이다.

## 여의도 (`assets/yeouido/`)

| 파일 | 내용 | 어디서 왔나 |
|---|---|---|
| `bg.png`, `bg_1x.png`, `tiles/` | 배경 그림(5504×3392 = 0.5 m/px, 2752×1696)과 확대용 타일(가장 세밀한 단계 22016×13568 = 12.5 cm/px) | 아래 데이터로 만든 3D 장면(판 F, 남쪽을 봄)을 렌더하고 경복궁과 같은 모델로 양식만 바꿔 다시 그린 뒤 128색으로 정리 |
| `depth_rg8.png`, `classes.png`, `crown.png` | 가림 판정용 깊이, 픽셀별 종류, 수관 마스크 | 같은 3D 장면의 깊이·ID 렌더 |
| `map.json` | 카메라, 랜드마크 앵커, 차로·철도·뱃길·보행 경로 | OSM 도로·철도·수면에서 뽑은 경로 + 직접 작성. OSM 형상을 담은 데이터라 **ODbL 1.0** |
| `winfaces.json` | 밤 창문 면 격자 | 위 깊이·분류 맵과 그림에서 계산 |

| 원천 | 라이선스 | 쓴 곳 |
|---|---|---|
| OpenStreetMap(건물 윤곽·높이 태그·`building:part`, 도로·철도·교량, 한강·샛강 수면, 공원·녹지, 나무) | ODbL 1.0 | 장면 배치 전부 |

- 건물 높이는 OSM `height` → `building:levels` 순으로 읽고, 둘 다 없으면 건물 종류와 바닥 면적으로 추정했다. 국토교통부 자료·국가유산청 자료·Overture 는 여의도에 쓰지 않았다.
- 랜드마크(63빌딩, 파크원, IFC, 더현대 서울, 콘래드, 국회의사당, LG 트윈타워, FKI 타워 등)는 자유 라이선스 사진과 지도 서비스 화면을 사람이 눈으로 보고 3D 로 모델링했다. 사진·거리뷰·위성 사진은 모델 입력이나 텍스처로 쓰지 않았고 저장소에도 없다. 그래서 사진 저작자 표시 대상이 아니다.
- GitHub Releases 의 여의도 랜드마크 `.glb` 는 이 모델을 건물(단지) 하나에 파일 하나로 낸 것이다. 윤곽·높이가 OSM 에서 왔으므로 장면 데이터와 같이 **ODbL 1.0**, 표시는 「© OpenStreetMap contributors」 + 「서울 미니어처 by midagedev」.
- 사람·차·자전거·배·지하철은 코드로 그린 연출이다.

## 그림 생성 모델

| 모델 | 라이선스 (확인) |
|---|---|
| Qwen/Qwen-Image-Edit-2511 (Comfy-Org 재패키징 fp8) | 모델 카드 태그 `apache-2.0`, 본문 "Qwen-Image is licensed under Apache 2.0." |
| lightx2v/Qwen-Image-Edit-2511-Lightning (Lightning 8-step LoRA) | 모델 카드 태그 `apache-2.0` |

확인하지 못한 것: 2511 저장소의 LICENSE 파일 본문(주소가 404). 카드의 문장은 "Qwen-Image"를 가리키고 2511 을 따로 명시하지는 않는다. 태그와 카드 외의 추가 제한은 보지 못했다.

## 배경음 생성 모델

| 모델 | 라이선스 (확인) |
|---|---|
| [ACE-Step/Ace-Step1.5](https://huggingface.co/ACE-Step/Ace-Step1.5) 커밋 `19671f4` — DiT `acestep-v15-turbo`, LM `acestep-5Hz-lm-1.7B`, VAE, 텍스트 인코더 `Qwen3-Embedding-0.6B` (모두 이 저장소의 파일) | 모델 카드 메타데이터 `license: mit`, 본문 "**License:** [MIT]". 코드 저장소 [ace-step/ACE-Step-1.5](https://github.com/ace-step/ACE-Step-1.5) LICENSE "MIT License, Copyright (c) 2026 ACEStep". 카드에 "You can strictly use the generated music for **commercial purposes**." |
| 텍스트 인코더 원본 Qwen/Qwen3-Embedding-0.6B, LM 의 출발 모델 Qwen/Qwen3-1.7B | 두 모델 카드 메타데이터 모두 `apache-2.0` |

- 생성 장비의 `acestep-v15-turbo/model.safetensors`, `acestep-5Hz-lm-1.7B/model.safetensors` sha256 이 위 커밋의 LFS 해시(`3f6e0797…`, `f161689d…`)와 같음을 확인했다.

- 제작자 장비에서 글 프롬프트만으로 만들었다(text-to-music, 가사 없음 `[Instrumental]`). 참조 오디오·샘플·녹음·기존 곡은 넣지 않았고, 프롬프트에 작곡가·게임·영화 이름을 쓰지 않았다.
- 생성 뒤 손댄 것: 구간 자르기(60–90초), 꼬리→머리 3.5초 크로스페이드로 루프 만들기, 루프 길이를 0.1초 격자에 맞추는 리샘플(0.1% 이내, 2센트 미만), 고정 게인으로 음량 맞추기(약 −18 LUFS, 리미터 없음), MP3 인코딩. 파일 앞뒤에 루프의 끝·머리 0.5초가 붙어 있다(`src/audio.js` 의 `loopPoints`).
- GitHub README 는 생성물의 독창성 확인과 AI 사용 표시를 권한다(라이선스 조건은 아님). 이 문서와 패널의 표기가 그 표시다.
- 모델 카드는 학습 데이터를 "licensed / royalty-free / synthetic"이라고 밝힌다. 이를 따로 검증하지는 않았다. 생성물이 기존 곡과 우연히 비슷할 가능성은 사람이 들어서만 확인할 수 있다.

## 영상·스크린샷을 올릴 때

화면 UI 를 숨기고 찍은 영상에는 출처가 보이지 않는다. 게시글 본문에 최소한 다음을 적는다.

> 지도 데이터 © OpenStreetMap contributors (ODbL) · Overture Maps · 국토교통부 GIS건물통합정보 · 국가유산청 경복궁 3D 기록(공공누리 1유형) · 그림 Qwen-Image-Edit-2511 + Lightning 8-step LoRA (Apache-2.0)

여의도만 찍었으면 OSM 과 그림 모델 표시면 된다. 이 프로젝트 표시(「서울 미니어처 by midagedev, CC BY 4.0」)를 더한 짧은 판·긴 판은 [docs/REUSE.md](docs/REUSE.md) 「출처 표시 문구」에 있다.

## 사실성 고지

건물 종류(빌라·한옥·중층·타워·아파트·공공·청와대)는 OSM 태그, 렌더 높이, 면적, 동네 구역으로 나눈 것이다. 태그가 없는 북촌·서촌의 작고 낮은 건물은 한옥으로 추정했다(등록 자료 아님). 지붕·벽 색은 종류 안에서 임의로 배정했다.
파사드·지붕·창문·수목은 AI 가 그린 장식이고 실측이 아니다. 사람과 차는 연출이며 실제 교통이 아니다.

## 쓰지 않은 것

- AI Hub 항공영상(71361, 491): 이 지역을 덮는 25 cm 타일이 없고(71361 은 10 m 위성영상뿐, 491 은 좌표 없는 60 m 조각), 이용정책이 "인공지능 학습모델의 학습용으로만"이라 공개 결과물의 입력으로 쓰지 않았다.
- 국토지리정보원 항공사진·정사영상: 공공누리 1유형일 가능성이 높지만 해당 영상의 유형·해상도·보안 처리 여부를 확인하지 못했다(다운로드에 회원 로그인이 필요). 쓰려면 다운로드 화면에서 유형을 확인한 뒤 출처 문구를 추가한다.

## 참조 사진 (위키미디어 공용)

이전 판에서 주요 건물을 다시 그릴 때 생김새 참조로 AI 에 보여 준 사진입니다. 지금 판의 그림은 사진 없이 3D 장면 렌더만 보고 그렸지만, 표기는 그대로 남겨 둡니다. 사진 파일은 페이지와 저장소에 들어 있지 않습니다. 퍼블릭 도메인, CC0, CC BY(동일조건 없는 것)만 골랐습니다. AI 가 참조한 그림이 사진의 2차적 저작물인지는 법적으로 확정된 바 없어, 보수적으로 모두 표기합니다.

| 건물 | 파일 | 저작자 | 라이선스 |
|---|---|---|---|
| 광화문 | [Kwanghwamun.JPG](https://commons.wikimedia.org/wiki/File:Kwanghwamun.JPG) | Pulgasari | Public domain |
| 경회루 | [Gyeongbokgung-Gyeonghoeru-02.jpg](https://commons.wikimedia.org/wiki/File:Gyeongbokgung-Gyeonghoeru-02.jpg) | eimoberg (a flickr user) | CC BY 2.0 |
| 근정전 | [Gyeongbokgung(palace) Geunjeongjeon(hall).jpg](https://commons.wikimedia.org/wiki/File:Gyeongbokgung(palace)_Geunjeongjeon(hall).jpg) | Brady Bellini | CC0 |
| 향원정 | [Hyangwonjeong-001.jpg](https://commons.wikimedia.org/wiki/File:Hyangwonjeong-001.jpg) | Craig Wyzik | CC BY 2.0 |
| 세종문화회관 | [August Proudly, to present Great Asia - Seoul Metropole - Master Asia Photography 2013 Sejong Center, ars artis - panoramio.jpg](https://commons.wikimedia.org/wiki/File:August_Proudly,_to_present_Great_Asia_-_Seoul_Metropole_-_Master_Asia_Photography_2013_Sejong_Center,_ars_artis_-_panoramio.jpg) | pictures Jettcom | CC BY 3.0 |
| 정부서울청사 | [Government Complex Seoul Main Building.jpg](https://commons.wikimedia.org/wiki/File:Government_Complex_Seoul_Main_Building.jpg) | Seoul Institute | CC BY 4.0 |
| 국립현대미술관 서울 | [MMCA Seoul.jpg](https://commons.wikimedia.org/wiki/File:MMCA_Seoul.jpg) | 서울연구원 | CC BY 4.0 |
| 동십자각 | [September Seoul Corea - Master Asia Photography 2012 - panoramio.jpg](https://commons.wikimedia.org/wiki/File:September_Seoul_Corea_-_Master_Asia_Photography_2012_-_panoramio.jpg) | pictures Jettcom | CC BY 3.0 |
| 집옥재 | [Jibokjae1.jpg](https://commons.wikimedia.org/wiki/File:Jibokjae1.jpg) | Stephen Mihalcik, Emeraldnabi | CC BY 2.0 |
| 국립민속박물관 | [Children's Museum of the National Folk Museum of Korea in April 2025.jpg](https://commons.wikimedia.org/wiki/File:Children%27s_Museum_of_the_National_Folk_Museum_of_Korea_in_April_2025.jpg) | DtSeoul | CC0 |
| 대한민국역사박물관 | [20240413 National Museum of Korean Contemporary History.jpg](https://commons.wikimedia.org/wiki/File:20240413_National_Museum_of_Korean_Contemporary_History.jpg) | Jjw | CC BY 4.0 |
| 정독도서관 | [Jeongdok Library.jpg](https://commons.wikimedia.org/wiki/File:Jeongdok_Library.jpg) | EllalineSeoul | CC0 |
| 영빈관 | [청와대 영빈관 외부 (3).jpg](https://commons.wikimedia.org/wiki/File:%EC%B2%AD%EC%99%80%EB%8C%80_%EC%98%81%EB%B9%88%EA%B4%80_%EC%99%B8%EB%B6%80_(3).jpg) | 미안 | CC0 |
| 국립고궁박물관 | [National Palace Museum of Korea 20240409 004.jpg](https://commons.wikimedia.org/wiki/File:National_Palace_Museum_of_Korea_20240409_004.jpg) | Mobius6 | CC BY 4.0 |
