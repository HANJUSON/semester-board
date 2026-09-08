"""강의자료 → 프로필 내용 생성.

호출 하나하나가 돈이라, 모든 작업 앞에 내용 해시 캐시를 둔다. 같은 PDF 를
다시 넣으면 모델을 부르지 않는다. 자료를 고쳐 올리면 해시가 바뀌어 자동으로
다시 만든다.
"""
import re
from pathlib import Path

from ..ingest.cache import Cache
from ..ingest.extract import Unsupported, extract, page_count
from . import prompts

# 1M 컨텍스트라 한 학기 자료도 통째로 들어간다. 자르지 않고, 큰 것만 알려준다.
BIG = 400_000


def _read(paths, verbose=True):
    """파일 목록 → (합친 텍스트, 실제로 읽은 파일 목록)."""
    chunks, used = [], []
    for p in paths:
        try:
            t = extract(p)
        except Unsupported as e:
            if verbose:
                print(f"    건너뜀 — {e}")
            continue
        pc = page_count(p)
        head = f"\n\n===== {Path(p).name}" + (f" ({pc}쪽)" if pc else "") + " =====\n"
        chunks.append(head + t)
        used.append(str(p))
    text = "".join(chunks)
    if verbose and len(text) > BIG:
        print(f"    주의: 입력이 {len(text):,}자입니다 — 호출 비용이 커집니다.")
    return text, used


def plan_course(llm, cache: Cache, key, name, syllabus_paths, weeks=16, verbose=True):
    """강의계획서 → 과목 메타 · 평가 비율 · 주차 뼈대 · 마감."""
    text, used = _read(syllabus_paths, verbose)
    if not text.strip():
        return None, []
    ck = Cache.key("course/v2", llm.model, name, weeks, text)
    hit = cache.get(ck)
    if hit:
        if verbose:
            print("    캐시 적중 — 모델 호출 없음")
        return hit, used
    out = llm.json(
        prompts.COURSE_SYSTEM,
        f"과목명: {name}\n학기는 {weeks}주다.\n\n다음은 이 과목의 강의계획서다.\n{text}",
        prompts.COURSE_SCHEMA, cache_long_input=True)
    return cache.put(ck, out), used


def write_week(llm, cache: Cache, course_name, w, material_paths,
               planned_topic="", verbose=True):
    """한 주차 강의자료 → 주차 카드 (t · q · pts)."""
    text, used = _read(material_paths, verbose)
    if not text.strip():
        return None, []
    ck = Cache.key("week/v2", llm.model, course_name, w, planned_topic, text)
    hit = cache.get(ck)
    if hit:
        if verbose:
            print("    캐시 적중 — 모델 호출 없음")
        return hit, used
    ask = (f"과목: {course_name}\n{w}주차 강의자료다.\n"
           + (f"강의계획서상 이 주차의 주제는 「{planned_topic}」이다.\n" if planned_topic else "")
           + f"\n{text}")
    out = llm.json(prompts.WEEK_SYSTEM, ask, prompts.WEEK_SCHEMA, cache_long_input=True)
    return cache.put(ck, out), used


def add_emphasis(llm, cache: Cache, course_name, w, recording_paths,
                 slide_paths=(), verbose=True):
    """강의 녹음 → 「교수님이 강조한 것」 블록."""
    rec, used = _read(recording_paths, verbose)
    if not rec.strip():
        return None, []
    slides, slide_used = _read(slide_paths, verbose) if slide_paths else ("", [])
    ck = Cache.key("emph/v1", llm.model, course_name, w, rec, slides)
    hit = cache.get(ck)
    if hit:
        if verbose:
            print("    캐시 적중 — 모델 호출 없음")
        return hit, used + slide_used
    ask = (f"과목: {course_name}\n{w}주차 강의 녹음 전사다.\n\n"
           + (f"[먼저 슬라이드 — 여기 이미 있는 내용은 hi 에 넣지 마라]\n{slides}\n\n"
              if slides else "")
           + f"[강의 녹음 전사]\n{rec}")
    out = llm.json(prompts.EMPH_SYSTEM, ask, prompts.EMPH_SCHEMA, cache_long_input=True)
    return cache.put(ck, out), used + slide_used


def find_concepts(llm, cache: Cache, profile, verbose=True):
    """전 과목 주차 계획 → 과목 간 겹치는 개념 지도."""
    lines = []
    for k in profile.get("courseOrder") or []:
        c = profile["courses"][k]
        lines.append(f"\n## {k} — {c['name']}")
        for w in c.get("weeks") or []:
            lines.append(f"  {w['w']}주차: {w['t']}")
    body = "\n".join(lines)
    if not body.strip():
        return None
    ck = Cache.key("concepts/v1", llm.model, body)
    hit = cache.get(ck)
    if hit:
        if verbose:
            print("  캐시 적중 — 모델 호출 없음")
        return hit
    out = llm.json(prompts.CONCEPT_SYSTEM,
                   "다음은 이번 학기 전 과목의 주차별 주제다.\n" + body,
                   prompts.CONCEPT_SCHEMA)
    return cache.put(ck, out)


TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def plain(s: str) -> str:
    """짧은 항목에서 태그를 걷어낸다.

    학수번호·담당·수업·교재와 주차 제목은 화면에서 escape 되어 나가는 자리라,
    태그가 섞이면 <code>TBA</code> 가 글자 그대로 보인다. 프롬프트로도 막지만
    모델이 늘 지킨다고 볼 수 없어 여기서 한 번 더 지운다.
    """
    return TAG.sub("", s or "").strip()


def merge_course(course: dict, plan: dict, weeks=16):
    """plan_course 결과를 프로필의 과목 dict 에 붙인다 (사람이 쓴 것은 덮지 않는다)."""
    for f in ("code", "prof", "time", "book"):
        if plan.get(f) and not course.get(f):
            course[f] = plain(plan[f])
    if plan.get("note") and not course.get("note"):
        course["note"] = plan["note"]          # note 는 태그를 그대로 렌더한다
    if plan.get("grading") and not course.get("grading"):
        course["grading"] = plan["grading"]

    have = {w["w"] for w in course.get("weeks") or []}
    for w in plan.get("weeks") or []:
        if w["w"] in have or not (1 <= w["w"] <= weeks):
            continue
        course.setdefault("weeks", []).append(
            {"w": w["w"], "t": plain(w["t"]), "q": w.get("q", ""),
             "src": "s", "pts": []})
    course["weeks"] = sorted(course.get("weeks") or [], key=lambda x: x["w"])

    if not course.get("tasks"):
        out = []
        for t in plan.get("tasks") or []:
            o = {"title": t["title"], "kind": t["kind"]}
            if t.get("tbd"):
                o["tbd"] = True
            elif t.get("week"):
                o["week"] = t["week"]
            if t.get("date"):
                o["date"] = t["date"]
            if t.get("pts"):
                o["pts"] = t["pts"]
            if t.get("note"):
                o["note"] = t["note"]
            if t.get("est"):
                o["est"] = True
            out.append(o)
        course["tasks"] = out

    pj = plan.get("project") or {}
    if pj.get("title") and not course.get("project"):
        course["project"] = {"title": pj["title"], "weight": pj.get("weight", ""),
                             "minor": False, "aim": pj.get("aim", ""),
                             "out": pj.get("out", []), "idea": pj.get("idea", []),
                             "check": pj.get("check", [])}
    return course


def merge_week(course: dict, w: int, card: dict):
    """write_week 결과를 해당 주차에 반영한다. 출처는 '자료 확인'(m)으로 올린다."""
    weeks = course.setdefault("weeks", [])
    tgt = next((x for x in weeks if x["w"] == w), None)
    if tgt is None:
        tgt = {"w": w}
        weeks.append(tgt)
        weeks.sort(key=lambda x: x["w"])
    tgt["t"] = plain(card.get("t") or "") or tgt.get("t", "")
    tgt["q"] = card.get("q") or tgt.get("q", "")
    tgt["pts"] = card.get("pts") or []
    tgt["src"] = "m"
    if card.get("mismatch"):
        tgt["pts"].append("<b>계획표와 어긋난 점</b> — " + card["mismatch"])
    return tgt
