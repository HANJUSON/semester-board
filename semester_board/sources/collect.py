"""LMS 수집 — Canvas + LearningX 를 훑어 렌더러가 쓰는 LMS 블록을 만든다.

여기서 나오는 것은 전부 '기계가 확인한 사실'이다. 주차별 해설이나 강조처럼
사람/LLM 이 만든 내용은 프로필 쪽에 있고, 이 파일은 손대지 않는다.
"""
import datetime
import re
import unicodedata

from .. import week as W
from ..config import course_title, week_re
from .canvas import Canvas, CanvasError
from .learningx import Boards, LearningX, attendance_items


STOP = {"AND", "OF", "THE", "FOR", "IN", "TO", "WITH", "ON", "A", "AN"}


def _key_for(title: str, raw: str, cid: int, taken: set) -> str:
    """과목 URL 키. 짧고 안정적이어야 한다 — 주소와 저장 키에 들어간다.

    한국 대학 LMS 는 과목명에 영문 정식명을 대문자로 함께 넣는 경우가 많다
    (…딥러닝응용(영강)(DEEP LEARNING APPLICATIONS(English))-01분반).
    거기서 머리글자를 뽑으면 c96163 대신 dla 가 되어 주소가 읽힌다.
    """
    words = [w for w in re.findall(r"[A-Z]{2,}", raw) if w not in STOP]
    if len(words) >= 2:
        cand = "".join(w[0] for w in words[:4]).lower()
    elif len(words) == 1:
        cand = words[0][:4].lower()
    else:
        ascii_words = re.findall(r"[A-Za-z]+", unicodedata.normalize("NFKD", title))
        cand = "".join(w[0] for w in ascii_words[:4]).lower()
    if len(cand) < 2:
        cand = "c%d" % cid
    base, n = cand, 2
    while cand in taken:
        cand, n = f"{base}{n}", n + 1
    taken.add(cand)
    return cand


def pull(school: dict, token=None, verbose=True):
    """{'lms': {...}, 'courses': [{key,id,title,...}]} 를 돌려준다."""
    cv = Canvas(school["canvas"], token)
    me = cv.whoami()
    if verbose:
        print(f"로그인: {me.get('name') or me.get('id')}")

    wre = week_re(school)
    lang_re = re.compile(school["langPattern"]) if school.get("langPattern") else None
    skip = school.get("excludeCourses") or []

    lms = {"courses": {}, "mods": {}, "vids": [], "att": [], "files": [],
           "asg": [], "posts": [], "done": [], "status": {}, "asof": ""}
    taken, found, week_votes = set(), [], []

    for c in cv.courses():
        raw = c.get("name") or ""
        if any(s in raw for s in skip):
            continue
        cid = c["id"]
        title = course_title(school, raw)
        key = _key_for(title, raw, cid, taken)
        short = title[:8]
        lms["courses"][key] = {"id": cid, "short": short, "name": title}
        teachers = [t.get("display_name") for t in (c.get("teachers") or [])
                    if t.get("display_name")]
        found.append({"key": key, "id": cid, "title": title,
                      "prof": " · ".join(teachers)})

        mods = cv.modules(cid)
        mmap = {}
        for mod in mods:
            m = wre.search(mod.get("name") or "")
            if not m:
                continue
            wk = int(next(g for g in m.groups() if g))
            mmap[str(wk)] = mod["id"]
            for it in (mod.get("items") or []):
                if it.get("type") == "File":
                    lms["files"].append({"c": key, "w": wk, "t": it["title"],
                                         "i": it.get("content_id") or it["id"]})
        if mmap:
            lms["mods"][key] = mmap

        for a in cv.assignments(cid):
            lms["asg"].append({"c": key, "n": a.get("name"),
                               "due": a.get("due_at"), "pts": a.get("points_possible"),
                               "i": a["id"],
                               "st": (a.get("submission_types") or ["none"])[0]})

        # 영상 · 출석 (LearningX 가 붙어 있는 학교만)
        items = attendance_items(mods, wre)
        vids = [i for i in items if i["is_video"]]
        for i in items:
            if not i["is_video"]:
                lms["att"].append({"c": key, "w": i["week"], "t": i["title"],
                                   "i": i["canvas_item"]})
                if i["week"]:
                    week_votes.append((i["week"], W.parse_ymd(i["title"])))
        for v in vids:
            lang = None
            if lang_re:
                m = lang_re.search(v["title"])
                lang = m.group(1) if m else None
            lms["vids"].append({"c": key, "w": v["week"], "t": v["title"],
                                "i": v["canvas_item"], "l": lang,
                                "a": 1, "du": "", "sec": 0})

        lx_cfg = school.get("learningx")
        if vids and lx_cfg:
            try:
                lx = LearningX(cv, lx_cfg["host"], lx_cfg.get("toolId", 2))
                summaries, meta = lx.fetch(cid, items)
                smap = {str(i): x.get("attendance_status") for i, x in summaries.items()}
                for v in vids:
                    st = smap.get(v["lx_item"])
                    if st and st != "none":
                        lms["status"][str(v["canvas_item"])] = st
                    if st == "attendance":
                        lms["done"].append(v["canvas_item"])
                for rec in lms["vids"]:
                    m = meta.get(str(rec["i"]))
                    if m:
                        rec.update(a=m["a"], du=m["due"], sec=m["sec"])
            except Exception as e:
                if verbose:
                    print(f"  [{key}] 출석 정보 실패: {type(e).__name__} {e}")

        # 게시판(강의자료실) — Canvas 모듈이 비어 있어도 여기 자료가 있을 수 있다
        n_post = 0
        if lx_cfg and lx_cfg.get("boardToolId"):
            try:
                bd = Boards(cv, lx_cfg["host"], lx_cfg["boardToolId"])
                for rec in bd.fetch(cid):
                    rec["c"] = key
                    lms["posts"].append(rec)
                    n_post += 1
            except Exception as e:
                if verbose:
                    print(f"  [{key}] 게시판 실패: {type(e).__name__} {e}")

        if verbose:
            print(f"  [{key}] {title} — 모듈 {len(mmap)}주 · 자료 "
                  f"{sum(1 for f in lms['files'] if f['c'] == key)} · 영상 {len(vids)} · "
                  f"과제 {sum(1 for a in lms['asg'] if a['c'] == key)}"
                  + (f" · 게시판 {n_post}" if n_post else ""))
            for rec in lms["posts"][-n_post:] if n_post else []:
                if rec["unread"]:
                    files = (" — " + ", ".join(rec["files"])) if rec["files"] else ""
                    print(f"        새 글  {rec['at']}  [{rec['board']}] {rec['title']}{files}")

    lms["done"] = sorted(set(lms["done"]))
    lms["asof"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return {"lms": lms, "courses": found, "weekVotes": week_votes}


def infer_week1_from(pull_result):
    """대면 출석 항목(제목이 날짜인 것)에서 1주차 월요일을 역산한다."""
    return W.infer_week1(pull_result.get("weekVotes") or [])


def describe_error(e: CanvasError) -> str:
    return {
        "expired": "토큰이 만료됐거나 잘못됐습니다. `semester-board login` 으로 다시 넣어 주세요.",
        "forbidden": "토큰은 살아 있지만 이 자원을 볼 권한이 없습니다 (LMS 설정 문제일 수 있습니다).",
        "network": "LMS 에 연결하지 못했습니다.",
    }.get(e.kind, f"LMS 오류: {e}")
