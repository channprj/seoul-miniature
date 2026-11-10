# 출처와 라이선스

2026-11-10 기준. 개인 비상업 연구 프로젝트다. 아래 표의 "확인"은 그날 각 페이지를 직접 읽어 확인한 내용이다.

## 브라우저로 나가는 것

| 파일 | 내용 | 어디서 왔나 |
|---|---|---|
| `redraw/bg.png`, `redraw/bg_1x.png` | 배경 픽셀아트(5504×3392 = 0.25 m/px, 저사양용 2752×1696) | 아래 데이터로 만든 색 블록 밑그림을 Qwen-Image-Edit-2511 로 다시 그리고 픽셀 격자로 정리 |
| `redraw/depth_rg8.png` | 가림 판정용 깊이 | 아래 데이터로 만든 3D 장면의 렌더 깊이 + OSM 건물 윤곽 돌출 |
| `redraw/classes.png` | 픽셀별 종류(도로·잔디·지붕 등) | 같은 깊이 + OSM |
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
| 사적 경복궁 광화문 월대 일원 3D 기록 (국가유산청, 2023) | 공공누리 제1유형 | 위와 같음 | 패널 |

- 공공누리 제1유형은 상업 이용과 2차적 저작물 작성을 모두 허용한다(출처 표시 조건).
- ODbL 의 동일조건은 "파생 데이터베이스"에 붙는다. 그림과 깊이 이미지는 OSMF FAQ 기준으로 Produced Work 이고, 여기서는 OSM 데이터를 고쳐서 재배포하지 않는다. 이 해석은 OSMF 의 설명이며 법률 자문이 아니다.
- V-World 건물 정보는 Hugging Face `serene9/daesang-tiles`(2026-09-09 스냅샷, 카드 표기 CC BY 4.0)를 거쳐 받았다. 원 저작물 조건(공공누리 1유형)을 따른다.
- 국가유산청 원본 모델(FBX·텍스처)과 작업용 3D 파일은 레포에도 배포물에도 없다.

## 그림 생성 모델

| 모델 | 라이선스 (확인) |
|---|---|
| Qwen/Qwen-Image-Edit-2511 (Comfy-Org 재패키징 fp8) | 모델 카드 태그 `apache-2.0`, 본문 "Qwen-Image is licensed under Apache 2.0." |
| lightx2v/Qwen-Image-Edit-2511-Lightning (8-step LoRA) | 모델 카드 태그 `apache-2.0` |

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

> 지도 데이터 © OpenStreetMap contributors (ODbL) · Overture Maps · 국토교통부 GIS건물통합정보 · 국가유산청 3D 기록(공공누리 1유형) · 그림 Qwen-Image-Edit-2511

## 사실성 고지

건물 종류(빌라·한옥·중층·타워·아파트·공공·청와대)는 OSM 태그, 렌더 높이, 면적, 동네 구역으로 나눈 것이다. 태그가 없는 북촌·서촌의 작고 낮은 건물은 한옥으로 추정했다(등록 자료 아님). 지붕·벽 색은 종류 안에서 임의로 배정했다.
파사드·지붕·창문·수목은 AI 가 그린 장식이고 실측이 아니다. 사람과 차는 연출이며 실제 교통이 아니다.

## 쓰지 않은 것

- AI Hub 항공영상(71361, 491): 이 지역을 덮는 25 cm 타일이 없고(71361 은 10 m 위성영상뿐, 491 은 좌표 없는 60 m 조각), 이용정책이 "인공지능 학습모델의 학습용으로만"이라 공개 결과물의 입력으로 쓰지 않았다.
- 국토지리정보원 항공사진·정사영상: 공공누리 1유형일 가능성이 높지만 해당 영상의 유형·해상도·보안 처리 여부를 확인하지 못했다(다운로드에 회원 로그인이 필요). 쓰려면 다운로드 화면에서 유형을 확인한 뒤 출처 문구를 추가한다.

## 참조 사진 (위키미디어 공용)

주요 건물을 다시 그릴 때 생김새 참조로 AI 에 보여 준 사진입니다. 사진 파일은 페이지와 저장소에 들어 있지 않습니다. 퍼블릭 도메인, CC0, CC BY(동일조건 없는 것)만 골랐습니다. AI 가 참조한 그림이 사진의 2차적 저작물인지는 법적으로 확정된 바 없어, 보수적으로 모두 표기합니다.

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
