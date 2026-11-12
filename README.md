# inha-route — 경인교대입구 탑승 시각 → 최적 통학 경로

경인교대입구역에서 인천1호선에 탄 순간, 아이폰 단축어 버튼 하나로
**수인분당선(원인재 환승)** vs **1호선 급행(부평 환승)→주안→511** 중 뭐가 빠른지 알려주는 시스템.
판단 기준은 두 시간표 — 원인재역 수인분당선 인천방면, 부평역 1호선 급행 인천방면 — 이고
511 구간은 상수 하나(`juan_to_school`)로 빼두었다.

계산은 전부 미리 해서 `lookup.json`(하루 1440분 → 답)에 넣어두고,
단축어는 현재 시각(HH:mm)을 키로 값을 꺼내 보여주기만 한다.

## 파일

| 파일 | 역할 |
|---|---|
| `config.json` | 구간별 소요시간(분). **실측해서 고치는 파일** |
| `timetable_weekday.txt` 등 | 수인분당선 원인재역 인천방면 출발 시각표 (평일/토/공휴일) |
| `timetable_line1_express_*.txt` | 1호선 부평역 인천방면 **급행·특급** 출발 시각표 (동인천행, 주안 정차) |
| `timetable_line1_local_*.txt` | 1호선 부평역 인천방면 **완행** 출발 시각표 (인천행) |
| `generate.py` | config + 시간표 → `lookup.json`, `lookup_sat.json`, `lookup_hol.json` |
| `fetch_tago.py` | 공공데이터포털 API로 시간표 갱신 (시간표 개정 때만) |
| `lookup*.json` | 단축어가 읽는 결과 파일. GitHub Pages 에 올림 |

## 1. 값 조정하고 생성

```bash
# config.json 수정 후
python3 generate.py
python3 generate.py --show 07:41   # 한 시각만 확인
```

`config.json`에서 꼭 실측으로 맞출 값:
- `ride_gyodae_to_bupyeong` / `ride_gyodae_to_woninjae` (기본 9 / 24)
- `transfer_bupyeong` / `transfer_woninjae` (환승 도보, 기본 4 / 3)
- `walk_inhadae_to_school` (인하대역→실제 가는 건물, 기본 7)
- `juan_to_school` (주안역 하차→학교 도착 전부, 기본 25 — **511은 여기 하나로 관리**)
- `express_ride_bupyeong_to_juan` / `local_ride_bupyeong_to_juan` (부평→주안 급행 5 / 완행 8)

### 1호선 급행 시간표 주의
공개 데이터에 급행 표시가 없어서 **동인천 종착 열차 = 급행/특급**으로 추렸다.
아침 7~9시대(용산→동인천)는 전부 급행/특급이 맞지만, 새벽 구로→동인천 일부는 일반일 수 있다.
`timetable_line1_express_weekday.txt`를 네이버 지도 부평역 시간표와 한 번 대조 권장.

## 2. GitHub Pages 에 올리기

1. GitHub 에 `INHA-optimal-route` 저장소 생성 (public), 이 폴더 push
2. Settings → Pages → Branch `main`, folder `/ (root)` → Save
3. 몇 분 뒤 `https://<아이디>.github.io/INHA-optimal-route/lookup.json` 이 열리면 끝

시간표나 config 바꿀 때마다 `python3 generate.py` → commit → push.

## 3. 아이폰 단축어 만들기

단축어 앱 → `+` → 아래 동작을 순서대로 추가. (검색창에 동작 이름 입력)

| # | 동작 | 설정 |
|---|---|---|
| 1 | **현재 날짜** (Date) | 그대로 |
| 2 | **날짜 포맷** (Format Date) | 날짜 포맷: **사용자 설정**, 포맷 문자열: `HH:mm` |
| 3 | **URL 내용 가져오기** (Get Contents of URL) | URL: `https://<아이디>.github.io/INHA-optimal-route/lookup.json`, 방법 GET |
| 4 | **사전 가져오기** (Get Dictionary from Input) | 입력: 3번 결과 |
| 5 | **사전 값 가져오기** (Get Dictionary Value) | 키: **2번 결과(포맷된 날짜)** 를 변수로 끌어다 넣기 |
| 6 | **알림 보기** (Show Notification) | 내용: 5번 결과 |

- 6번을 **결과 보기**(Show Result)로 하면 큰 팝업으로 뜸. 열차 안에서는 알림이 편함.
- 단축어 이름: `탑승` → Siri 에게 "탑승" 이라고 말해도 됨.

### 버튼 하나로
- **액션 버튼**(15 Pro↑): 설정 → 액션 버튼 → 단축어 → `탑승`
- **뒷면 탭**: 설정 → 손쉬운 사용 → 터치 → 뒷면 탭 → 이중 탭 → `탑승`
- **잠금화면 위젯**: 잠금화면 길게 → 사용자화 → 위젯 추가 → 단축어 → `탑승`

### 주말까지 자동 분기 (선택)
2번 뒤에 **날짜 포맷**을 하나 더 넣고 포맷 문자열 `EEEE` (요일) →
**만약** 결과가 `토요일` 이면 URL을 `lookup_sat.json`, `일요일`이면 `lookup_hol.json`, 아니면 `lookup.json`.
공휴일은 자동 판별이 안 되니 그날은 직접 `lookup_hol.json` 을 보거나 그냥 평일 걸 쓰고 참고만.

## 4. 시간표 갱신 (개정 때)

```bash
export TAGO_KEY='공공데이터포털 인증키'
python3 fetch_tago.py --list          # 원인재 역 ID 확인
python3 fetch_tago.py --station <ID>  # timetable_*.txt 3개 갱신
python3 generate.py
```

## 다음 단계 아이디어

- **"부평 도착" 버튼**: 부평 도착 시점엔 원인재까지 15분 안쪽이라 실시간 도착정보가 의미 있음.
  Cloudflare Worker 하나 띄워서 수인분당선·511 실시간 API 를 합쳐 주면 단축어는 URL만 바꾸면 됨.
- 실제 도착시각 로그를 쌓아 config 값 자동 보정.

## 웹 페이지 (단축어 없이 쓰기)

- `https://steam6879.github.io/INHA-optimal-route/` — 경인교대입구 탑승 기준
- `https://steam6879.github.io/INHA-optimal-route/?at=bp` — 부평 도착 기준 (계속 탈지 / 내릴지)
- 테스트: 주소 뒤에 `?t=07:41` (부평은 `?at=bp&t=07:50`)

부평 기준 결과는 `lookup_bp*.json` 에서 읽는다. 조회 시각에서 `ride_gyodae_to_bupyeong` 만큼 뺀 시각으로 같은 계산을 하므로,
인천1호선이 늦어 실제 부평 도착이 밀리면 그만큼 반영된 답이 나온다.
