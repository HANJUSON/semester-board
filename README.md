# semester-board

**LMS와 내 강의자료로, 한 장짜리 학기 상황판을 만드는 로컬 CLI.**

한 학기에 과목이 일곱 개면 마감도 일곱 군데에 흩어진다. LMS는 "무엇이 올라왔는지"는
알려주지만 "이번 주에 무엇을 해야 하는지"는 알려주지 않는다. 이 도구는 둘을 합쳐
파일 하나(`dashboard.html`)로 만든다. 브라우저로 열면 끝이고, 서버도 계정도 없다.

> *A local CLI that turns your Canvas LMS data and lecture materials into a single-file
> semester dashboard. Everything runs on your machine; your access token never leaves it.*

---

## 왜 로컬 도구인가

한국 대학이 쓰는 Canvas는 **CORS 헤더를 보내지 않는다.** 브라우저에서 직접 부를 수 없다는
뜻이라, 웹 서비스로 만들면 프록시 서버가 반드시 끼고 그 순간 남의 LMS 토큰이 남의 서버를
지나간다. 그건 사실상 학생 계정 전권을 맡기는 일이다.

그래서 이 도구는 로컬에서만 돈다.

- 액세스 토큰은 `~/.config/semester-board/token`(권한 600)에만 있고 네트워크로 나가는 곳은 학교 LMS뿐이다.
- 강의자료 원문은 어디에도 업로드되지 않는다. `generate`를 쓸 때만, 필요한 텍스트가 모델로 간다.
- 결과물은 내 PC의 HTML 파일 하나다.

---

## 설치

```bash
git clone https://github.com/HANJUSON/semester-board.git
cd semester-board
pip install -e .
```

기본 기능은 **표준 라이브러리만** 쓴다. 선택 사항:

| 추가 | 언제 필요한가 |
|---|---|
| `pip install -e '.[generate]'` | 강의자료를 읽어 주차 내용을 만들 때 (Anthropic API) |
| `sudo apt install poppler-utils` | PDF 읽기 (권장). 없으면 `.[pdf]`로 pypdf 사용 |
| `pip install -e '.[hwp]'` | `.hwp` 강의계획서를 바로 읽을 때 |

`.pptx` · `.docx` · `.hwpx`는 추가 설치 없이 읽는다.

---

## 5분 사용법

```bash
mkdir ~/내학기 && cd ~/내학기

semester-board login                       # LMS 액세스 토큰 저장 (화면에 안 보임)
semester-board init --school ku --label "2026-2학기"
semester-board pull                        # 과목·자료·영상·출석·과제 가져오기
semester-board serve                       # 브라우저로 열기
```

여기까지가 **LMS만으로 되는 부분**이다. 그런데 실제로 해 보면 이게 전부가 아니다.

### LMS는 생각보다 비어 있다

7과목 112개 주차 칸 중 LMS API로 채워진 것은 **31칸(28%)** 이었다.

| 과목 | 영상 | 자료 | 내용이 있는 주차 |
|---|---|---|---|
| 빅데이터분산처리시스템 | 29 | 1 | 14/16 |
| 인공지능개론 | 28 | 14 | 14/16 |
| 딥러닝응용 | 0 | 2 | 2/16 |
| 데이터베이스 · 거대언어모델 · 소프트웨어응용 | 0 | 0 | **0/16** |

교수님이 자료를 LMS에 안 올리거나, 파일 탭을 꺼 두거나, 블랙보드를 따로 쓰기 때문이다.
나머지 72%를 채우는 것이 다음 단계다.

### 내 강의자료로 나머지를 채운다

```bash
# 강의계획서 → 평가 비율 · 16주 뼈대 · 마감 일정
semester-board ingest dla ~/강의/딥러닝/강의계획서.pdf --syllabus

# 주차별 자료 → 그 주차의 핵심 질문과 요약
semester-board ingest dla ~/강의/딥러닝/2주차.pdf -w 2

# 강의 녹음 전사 → 「교수님이 강조한 것」 블록
semester-board ingest dla ~/강의/딥러닝/9.7.txt -w 2 --recording

semester-board generate --concepts          # 모델 호출 (비용 발생)
semester-board build
```

`generate`는 같은 파일을 두 번 보내지 않는다. 내용 해시로 캐시하므로, 자료를 고쳐
올렸을 때만 다시 만든다.

---

## 이 도구가 특별히 신경 쓰는 것

**출처를 흐리지 않는다.** 주차 카드마다 배지가 붙는다 — `자료 확인`(강의자료를 실제로 읽음) ·
`계획서 기준`(강의계획서에만 있음) · `진도 추정`(교재로 미뤄 짐작). 추정을 확인처럼
보이게 만드는 것이 이런 도구의 가장 큰 거짓말이라, 스키마 차원에서 갈라 뒀다.

**1주차를 사람이 안 정한다.** 상황판의 모든 주차 표시가 1주차 월요일 하나에 매달려 있어서
하루만 틀려도 화면 전체가 한 주 밀린다. LMS의 출석 항목 날짜에서 역산하고, 근거가
갈리면 임의로 고르지 않고 사람에게 묻는다.

**401을 두 가지로 나눈다.** Canvas는 '토큰 만료'와 '권한 없음'을 똑같이 401로 준다.
실제로 학생 계정은 대부분 과목에서 `/files`가 401인데(파일 탭이 꺼져 있다), 이걸 만료로
읽으면 멀쩡한 토큰을 버리게 된다. 401을 만나면 `/users/self`로 토큰을 한 번 더 확인한다.

**강의 녹음은 슬라이드에 없는 말만 남긴다.** 슬라이드에 이미 있는 내용을 반복하면 그 블록은
쓸모가 없다. 외우라고 한 것과 **외울 필요 없다고 못 박은 것**을 따로 모은다.

---

## 명령어

| 명령 | 하는 일 |
|---|---|
| `login` | LMS 액세스 토큰을 설정 폴더에 저장 (권한 600) |
| `init` | 학기 프로필 생성. 1주차 월요일을 LMS에서 추론 |
| `pull` | 과목·모듈·자료·영상·출석·과제를 가져와 `*.lms.json`에 저장 |
| `ingest` | 내 PC의 강의자료를 과목·주차에 등록 |
| `generate` | 등록한 자료를 읽어 주차 내용 생성 (`--dry-run`으로 대상만 확인) |
| `build` | `dashboard.html` 생성 (`--fragment`는 claude.ai 아티팩트용) |
| `serve` | 빌드하고 브라우저로 열기 |
| `doctor` | 토큰·프로필·LMS 연결 점검 |

## 구조

```
profiles/<이름>.json        사람이 쓴 내용 — 과목·주차·마감·프로젝트·개념
profiles/<이름>.lms.json    LMS에서 긁어온 사실 (pull 이 덮어씀)
cache/                      모델 응답 캐시 (내용 해시)
build/dashboard.html        결과물
```

프로필은 그냥 JSON이라 손으로 고쳐도 된다. 모델이 쓴 문장이 마음에 안 들면 직접 고치는
쪽이 빠르고, `generate`는 이미 채워진 주차를 건드리지 않는다(`--all`을 주면 다시 만든다).

과목 키(`dla`, `bdps` …)는 과목명의 영문에서 자동으로 뽑는다. 주소와 저장 키에 들어가므로
바꾸려면 `pull` 직후에 바꾸는 것이 좋다.

## 다른 학교에서 쓰려면

학교마다 다른 것은 코드가 아니라 `semester_board/schools/*.json`이다.

```json
{
  "canvas": "https://canvas.example.ac.kr",
  "learningx": { "host": "https://mylms.example.ac.kr", "toolId": 2 },
  "weekPattern": "(\\d+)\\s*주차",
  "courseNamePattern": "\\(학부\\)(?P<title>[^(]+)",
  "excludeCourses": ["교양필수 안내"]
}
```

`generic.json`을 복사해 고친 뒤 `--school <파일이름>`으로 쓴다. LearningX가 없는 학교는
`"learningx": null`로 두면 영상·출석 단계를 건너뛴다. PR 환영.

## 개발

```bash
python3 tests/test_basic.py     # 네트워크·모델 호출 없이 도는 검사
```

`semester_board/templates/dashboard.html`은 렌더러다. 데이터가 하나도 들어 있지 않고,
빌드할 때 `PROFILE`과 `LMS` 두 블록만 주입된다.

## 라이선스

MIT. 이 저장소에는 강의자료가 들어 있지 않으며, 생성된 프로필도 포함하지 않는다.
강의자료의 저작권은 각 교수·기관에 있고, 이 도구로 만든 요약은 개인 학습용이다.
