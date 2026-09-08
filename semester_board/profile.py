"""프로필 — 상황판에 들어가는 '사람이 쓴 내용' 전부.

LMS 에서 긁어온 사실(lms.json)과 짝을 이룬다. 이 파일만 있으면 어떤 학기든
같은 렌더러로 그려진다. 스키마를 얇게 유지하고, 모르는 필드는 그대로 통과시킨다.
"""
import json
from pathlib import Path

SCHEMA = 1

WEEK_SRC = {"m", "s", "g"}      # m=자료 확인 · s=계획서 기준 · g=추정
TASK_KINDS = {"과제", "시험", "프로젝트", "발표", "퀴즈", "토론", "기타"}


def blank(pid, school, semester_label, week1_monday, weeks=16, exam_weeks=None):
    return {
        "schema": SCHEMA,
        "id": pid,
        "semester": {"label": semester_label, "week1Monday": week1_monday,
                     "weeks": weeks, "examWeeks": exam_weeks or {}},
        "school": {"id": school.get("id"), "name": school.get("name"),
                   "short": school.get("short"), "canvas": school.get("canvas")},
        "courseOrder": [],
        "courses": {},
        "highlights": [],
        "concepts": [],
        "terms": [],
    }


def blank_course(name, short=None, code="", prof="", time="", book="", note=""):
    return {"name": name, "short": short or name[:8], "code": code, "prof": prof,
            "time": time, "book": book, "note": note,
            "grading": [], "materials": [], "project": None,
            "weeks": [], "local": {}, "tasks": []}


def load(path) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"프로필이 없습니다: {p}\n먼저 `semester-board init` 을 실행하세요.")
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def validate(prof: dict):
    """치명적 오류는 err, 고쳐두면 좋은 것은 warn 으로 나눠 돌려준다."""
    err, warn = [], []
    if prof.get("schema") != SCHEMA:
        warn.append(f"schema 가 {prof.get('schema')} 입니다 (이 도구는 {SCHEMA}).")

    sem = prof.get("semester") or {}
    if not sem.get("week1Monday"):
        err.append("semester.week1Monday 가 없습니다 — 모든 주차 표시가 여기에 달려 있습니다.")
    else:
        try:
            from .week import parse_ymd
            d = parse_ymd(sem["week1Monday"])
            if d.weekday() != 0:
                warn.append(f"semester.week1Monday({sem['week1Monday']})가 월요일이 아닙니다 — "
                            "주차가 하루 밀려 보일 수 있습니다.")
        except Exception:
            err.append(f"semester.week1Monday 형식이 잘못됐습니다: {sem.get('week1Monday')!r}")

    nw = sem.get("weeks") or 16
    order = prof.get("courseOrder") or []
    courses = prof.get("courses") or {}
    for k in order:
        if k not in courses:
            err.append(f"courseOrder 에 있는 '{k}' 가 courses 에 없습니다.")
    for k in courses:
        if k not in order:
            warn.append(f"courses['{k}'] 가 courseOrder 에 없어 화면에 나오지 않습니다.")

    for k, c in courses.items():
        if not c.get("name"):
            err.append(f"courses['{k}'].name 이 비어 있습니다.")
        seen = set()
        for w in c.get("weeks") or []:
            n = w.get("w")
            if not isinstance(n, int) or not (1 <= n <= nw):
                err.append(f"[{k}] 주차 번호가 범위 밖입니다: {n!r}")
            if n in seen:
                err.append(f"[{k}] {n}주차가 중복입니다.")
            seen.add(n)
            if w.get("src") not in WEEK_SRC:
                warn.append(f"[{k}] {n}주차 src 가 {w.get('src')!r} 입니다 "
                            f"(m/s/g 중 하나여야 출처 배지가 정확합니다).")
            if not (w.get("pts") or []):
                warn.append(f"[{k}] {n}주차 내용(pts)이 비어 있습니다.")
        total = sum(g.get("pct") or 0 for g in c.get("grading") or [])
        if c.get("grading") and total != 100:
            warn.append(f"[{k}] 평가 비율 합계가 {total}% 입니다.")
        for t in c.get("tasks") or []:
            if t.get("kind") and t["kind"] not in TASK_KINDS:
                warn.append(f"[{k}] 알 수 없는 마감 종류: {t['kind']!r}")
    return err, warn


def stats(prof: dict) -> str:
    cs = prof.get("courses") or {}
    nw = sum(len(c.get("weeks") or []) for c in cs.values())
    nt = sum(len(c.get("tasks") or []) for c in cs.values())
    filled = sum(1 for c in cs.values() for w in (c.get("weeks") or []) if w.get("pts"))
    return (f"과목 {len(cs)} · 주차카드 {nw}개(내용 있는 것 {filled}) · 마감 {nt}개 · "
            f"개념 {len(prof.get('concepts') or [])} · 용어 {len(prof.get('terms') or [])}")
