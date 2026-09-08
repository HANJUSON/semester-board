# -*- coding: utf-8 -*-
"""프롬프트와 출력 스키마.

상황판의 값어치는 '자료에 뭐가 있었는지'가 아니라 '무엇이 중요한지'를 말해주는
데서 나온다. 그래서 프롬프트가 요약이 아니라 판단을 요구하도록 써 뒀다.
출처를 흐리는 것이 이 도구에서 가장 나쁜 실패라, 확인한 것과 추측한 것을
반드시 나누게 한다.
"""

VOICE = """너는 한 학생의 학기 상황판을 만든다. 읽는 사람은 이 과목을 수강 중인
본인 한 명이고, 목적은 '이번 주에 무엇을 해야 하는가'를 3초 안에 아는 것이다.

문체 규칙:
- 한국어. 문어체 평서문('~한다', '~이다'). 존댓말과 이모지는 쓰지 않는다.
- 각 항목은 완결된 문장 1~3개. 명사 나열로 끝내지 않는다.
- 문장에서 가장 중요한 구절 하나만 <b>…</b> 로 감싼다. 강조가 셋을 넘으면 강조가 아니다.
- 용어·명령어·파일명은 <code>…</code> 로 감싼다.
- 태그는 <b>설명하는 문장</b> 안에서만 쓴다. 제목·학수번호·담당·수업시간·교재처럼
  짧은 항목에는 태그를 넣지 않는다. 그 자리에서는 태그가 글자 그대로 보인다.
- 슬라이드 제목을 옮겨 적지 말고, 그 슬라이드가 무엇을 주장하는지를 쓴다.
- 시험에 나올 만한 것, 과제와 이어지는 것, 여기서 막히면 뒤가 밀리는 것을 앞에 둔다.

정직성 규칙 (가장 중요):
- 자료에서 확인한 것과 추측한 것을 섞지 않는다.
- 자료에 없으면 지어내지 않는다. 비워 두거나, 추측이라고 밝힌다.
- 날짜·배점·마감은 자료에 적힌 그대로만 쓴다. 어림으로 채우지 않는다."""

# ── 1. 강의계획서 → 과목 뼈대 ─────────────────────────────────────
COURSE_SYSTEM = VOICE + """

지금 하는 일: 강의계획서 한 편을 읽고 과목의 뼈대를 만든다.
- grading 의 pct 합은 계획서에 적힌 대로 둔다. 합이 100 이 아니면 그대로 둔다.
- weeks 는 계획서의 주차 계획표를 그대로 옮긴다. 표에 없는 주차는 넣지 않는다.
- t 는 <b>제목</b>이지 설명이 아니다. 30자 이내의 명사구 하나로 쓰고, 문장으로
  늘이지 않으며 <b> 같은 태그를 넣지 않는다. 화면의 목록과 사이드바에 그대로 들어간다.
  좋은 예: 「3DGS — 사진에서 3D 공간으로」  나쁜 예: 「3D Gaussian Splatting으로 2D
  사진을 3D 공간으로 바꾸는 원리를 다룬다. A1 과제의 기반이 된다.」
- q 는 그 주차를 한 문장으로 요약하는 질문이다. 답이 그 주차 내용이어야 한다.
- tasks 에는 계획서에 날짜나 주차가 적힌 것만 넣는다. 날짜가 없으면 week 만 넣고
  est 를 true 로 둔다. 주차조차 모르면 tbd 를 true 로 두고 week 는 0 으로 둔다.
- project 가 없는 과목이면 title 을 빈 문자열로 둔다."""

COURSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["code", "prof", "time", "book", "note", "grading", "weeks",
                 "tasks", "project"],
    "properties": {
        "code": {"type": "string", "description": "학수번호. 없으면 빈 문자열"},
        "prof": {"type": "string"},
        "time": {"type": "string", "description": "요일·교시·강의실. 없으면 빈 문자열"},
        "book": {"type": "string", "description": "교재. 없으면 빈 문자열"},
        "note": {"type": "string",
                 "description": "이 과목에서 학생이 놓치면 손해 보는 규칙 한 문장. "
                                "지각 제출 처리, 메일 규칙, 출석 방식 같은 것."},
        "grading": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["label", "pct", "kind"],
            "properties": {"label": {"type": "string"},
                           "pct": {"type": "integer"},
                           "kind": {"type": "string",
                                    "enum": ["exam", "proj", "hw", "att"]}}}},
        "weeks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["w", "t", "q"],
            "properties": {"w": {"type": "integer"},
                           "t": {"type": "string"},
                           "q": {"type": "string"}}}},
        "tasks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "kind", "week", "date", "pts", "note", "est", "tbd"],
            "properties": {
                "title": {"type": "string"},
                "kind": {"type": "string",
                         "enum": ["과제", "시험", "프로젝트", "발표", "퀴즈", "토론", "기타"]},
                "week": {"type": "integer"},
                "date": {"type": "string",
                         "description": "YYYY-MM-DD. 계획서에 날짜가 없으면 빈 문자열"},
                "pts": {"type": "string", "description": "배점 표기. 없으면 빈 문자열"},
                "note": {"type": "string"},
                "est": {"type": "boolean", "description": "주차만 알고 날짜는 추정"},
                "tbd": {"type": "boolean", "description": "마감 자체가 미공지"}}}},
        "project": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "weight", "aim", "out", "idea", "check"],
            "properties": {
                "title": {"type": "string", "description": "프로젝트가 없으면 빈 문자열"},
                "weight": {"type": "string"},
                "aim": {"type": "string",
                        "description": "이 프로젝트가 무엇을 증명하라는 과제인지 2~3문장"},
                "out": {"type": "array", "items": {"type": "string"},
                        "description": "제출물 목록"},
                "idea": {"type": "array", "items": {"type": "string"},
                         "description": "강의 진도와 이어지는 주제 후보 2~3개"},
                "check": {"type": "array", "items": {"type": "string"},
                          "description": "스스로 확인할 질문 2~3개"}}}}}

# ── 2. 강의자료 → 주차 카드 ───────────────────────────────────────
WEEK_SYSTEM = VOICE + """

지금 하는 일: 한 주차의 강의자료를 읽고 그 주차 카드를 쓴다.
- pts 는 4~6개. 그 주차에서 실제로 이해해야 하는 것만.
- 첫 항목은 그 주차의 중심 주장이어야 한다. 목차 설명으로 시작하지 않는다.
- 자료에 실습·환경 설정이 있으면 '여기서 막히면 다음 주가 밀린다'는 식으로
  실질적인 위험을 짚는다.
- t 는 자료가 실제로 다룬 내용에 맞춘다. 계획서 제목과 다르면 자료 쪽을 따른다.
  제목은 30자 이내 명사구다. 문장으로 늘이거나 태그를 넣지 않는다."""

WEEK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["t", "q", "pts", "mismatch"],
    "properties": {
        "t": {"type": "string", "maxLength": 40,
              "description": "주차 제목. 30자 이내 명사구, 태그 없음"},
        "q": {"type": "string"},
        "pts": {"type": "array", "items": {"type": "string"}},
        "mismatch": {"type": "string",
                     "description": "계획서의 그 주차 주제와 자료 내용이 어긋나면 "
                                    "무엇이 어떻게 다른지 한 문장. 같으면 빈 문자열"}}}

# ── 3. 강의 녹음 → 강조 블록 ──────────────────────────────────────
EMPH_SYSTEM = VOICE + """

지금 하는 일: 교수의 강의 녹음 전사를 읽고, <b>슬라이드에는 없는 말</b>만 골라낸다.
이 블록의 존재 이유는 '자료를 읽으면 아는 것'과 '그 자리에 있어야 아는 것'을
가르는 데 있다. 슬라이드에 이미 적힌 내용을 다시 쓰면 이 작업은 실패다.

hi (강조) 에 넣을 것:
- 외우라고 명시한 것, 두 번 이상 반복한 것, 시험에 나온다고 말한 것
- 슬라이드에 없는 비유·예시·수치
- 자료의 어느 부분을 어떻게 읽으라고 지시한 것
- 진도가 어디까지 나갔고 나머지는 언제 다루는지

lo (부담을 덜어준 말) 에 넣을 것:
- 외울 필요 없다고 못 박은 것
- 몰라도 된다, 뒤에서 다시 다룬다고 안심시킨 것
- 난이도·범위를 낮추겠다고 한 것

전사는 음성인식 결과라 오탈자가 많다. 문맥으로 고쳐 읽되, 확실하지 않은 고유명사는
쓰지 않는다. 교수가 실제로 한 말을 인용할 때만 큰따옴표를 쓴다."""

EMPH_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["hi", "lo"],
    "properties": {
        "hi": {"type": "array", "items": {"type": "string"}},
        "lo": {"type": "array", "items": {"type": "string"}}}}

# ── 4. 과목 간 겹치는 개념 ────────────────────────────────────────
CONCEPT_SYSTEM = VOICE + """

지금 하는 일: 여러 과목의 주차 계획을 한꺼번에 보고, <b>둘 이상의 과목에서
겹치는 개념</b>을 찾는다. 한 번 공부해서 여러 과목에 쓰는 지점을 알려주는 것이
목적이므로, 한 과목에서만 나오는 것은 넣지 않는다.

- 각 개념마다 최소 두 과목의 hits 가 있어야 한다.
- hits[].w 는 그 과목에서 그 개념이 실제로 나오는 주차 번호만 넣는다.
- r 은 그 과목에서 이 개념이 어떤 얼굴로 나오는지 한 문장.
- tip 은 이 겹침을 어떻게 활용하라는 실행 지침 한 문장."""

CONCEPT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["concepts"],
    "properties": {"concepts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "k", "n", "d", "hits", "tip"],
        "properties": {
            "id": {"type": "string", "description": "영문 소문자 2~4자 식별자"},
            "k": {"type": "string", "description": "분류 (예: 모델 구조, 데이터 처리)"},
            "n": {"type": "string", "description": "개념 이름"},
            "d": {"type": "string", "description": "이 개념이 무엇인지 2~3문장"},
            "hits": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["c", "w", "r"],
                "properties": {"c": {"type": "string"},
                               "w": {"type": "array", "items": {"type": "integer"}},
                               "r": {"type": "string"}}}},
            "tip": {"type": "string"}}}}}}
