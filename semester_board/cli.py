# -*- coding: utf-8 -*-
"""semester-board 명령줄 도구."""
import argparse
import datetime
import getpass
import json
import os
import sys
from pathlib import Path

from . import __version__, profile as P, render, week as W
from .config import list_schools, load_school
from .ingest.cache import Cache
from .paths import Workspace, token_file
from .sources.canvas import CanvasError
from .sources.collect import describe_error, infer_week1_from, pull


def _ws(a):
    return Workspace(a.dir).ensure()


def _pid(a, ws):
    if a.profile:
        return a.profile
    found = sorted(p.stem for p in ws.profiles.glob("*.json")
                   if not p.stem.endswith(".lms"))
    if not found:
        sys.exit("프로필이 없습니다. `semester-board init` 을 먼저 실행하세요.")
    if len(found) > 1 and not a.profile:
        sys.exit(f"프로필이 여러 개입니다: {', '.join(found)}\n--profile 로 지정하세요.")
    return found[0]


def _load(a):
    ws = _ws(a)
    pid = _pid(a, ws)
    prof = P.load(ws.profile_path(pid))
    lms_p = ws.lms_path(pid)
    lms = json.loads(lms_p.read_text(encoding="utf-8")) if lms_p.exists() else None
    return ws, pid, prof, lms


# ── login ────────────────────────────────────────────────────────
def cmd_login(a):
    f = token_file()
    if a.show:
        print(f"토큰 파일: {f}  ({'있음' if f.exists() else '없음'})")
        return
    print("LMS 액세스 토큰을 붙여 넣으세요 (화면에 보이지 않습니다).")
    print("  Canvas → 계정 → 설정 → '새 액세스 토큰 만들기' 에서 발급합니다.")
    tok = getpass.getpass("토큰: ").strip()
    if not tok:
        sys.exit("입력이 비어 있어 저장하지 않았습니다.")
    f.write_text(tok, encoding="utf-8")
    os.chmod(f, 0o600)
    print(f"저장했습니다: {f} (권한 600)")


# ── init ─────────────────────────────────────────────────────────
def cmd_init(a):
    ws = _ws(a)
    school = load_school(a.school)
    pid = a.id or f"{school['id']}-{a.label.replace(' ', '')}"
    path = ws.profile_path(pid)
    if path.exists() and not a.force:
        sys.exit(f"이미 있습니다: {path}  (덮어쓰려면 --force)")

    w1 = a.week1
    if not w1:
        print("LMS 에서 1주차 월요일을 추론합니다…")
        try:
            res = pull(school, verbose=False)
            got = infer_week1_from(res)
            if got:
                w1 = W.ymd(got)
                print(f"  출석 항목 날짜로 역산: {w1} ({'월요일' if got.weekday() == 0 else '?'})")
            else:
                print("  판단할 근거가 부족합니다.")
        except CanvasError as e:
            print("  " + describe_error(e))
    if not w1:
        today = datetime.date.today()
        w1 = W.ymd(W.monday_of(today))
        print(f"  임시로 이번 주 월요일({w1})을 넣었습니다 — 맞는지 확인하세요.")

    prof = P.blank(pid, school, a.label, w1, weeks=school.get("semesterWeeks", 16),
                   exam_weeks=school.get("examWeeks"))
    P.save(path, prof)
    print(f"\n프로필을 만들었습니다: {path}")
    print("다음: semester-board pull")


# ── pull ─────────────────────────────────────────────────────────
def cmd_pull(a):
    ws = _ws(a)
    pid = _pid(a, ws)
    prof = P.load(ws.profile_path(pid))
    school = load_school(prof.get("school", {}).get("id") or "generic")
    print(f"{school['name']} LMS 에서 가져오는 중…")
    try:
        res = pull(school)
    except CanvasError as e:
        sys.exit(describe_error(e))

    ws.lms_path(pid).write_text(
        json.dumps(res["lms"], ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    added = []
    for c in res["courses"]:
        k = c["key"]
        if k not in prof["courses"]:
            prof["courses"][k] = P.blank_course(c["title"], prof=c.get("prof", ""))
            prof["courseOrder"].append(k)
            added.append(f"{k}({c['title']})")
        elif c.get("prof") and not prof["courses"][k].get("prof"):
            # LMS 가 담당교수를 알고 있는데 프로필이 비어 있으면 채운다
            prof["courses"][k]["prof"] = c["prof"]

    got = infer_week1_from(res)
    cur = prof["semester"].get("week1Monday")
    if got and W.ymd(got) != cur:
        print(f"\n주의: LMS 기준 1주차 월요일은 {W.ymd(got)} 인데 프로필은 {cur} 입니다.")
        if a.fix_week1:
            prof["semester"]["week1Monday"] = W.ymd(got)
            print("  --fix-week1 이라 LMS 쪽으로 맞췄습니다.")
        else:
            print("  --fix-week1 을 주면 LMS 쪽으로 맞춥니다.")

    P.save(ws.profile_path(pid), prof)
    print(f"\nLMS 저장: {ws.lms_path(pid)}")
    if added:
        print("새 과목: " + ", ".join(added))
    print(P.stats(prof))


# ── ingest ───────────────────────────────────────────────────────
def cmd_ingest(a):
    ws = _ws(a)
    pid = _pid(a, ws)
    prof = P.load(ws.profile_path(pid))
    c = prof["courses"].get(a.course)
    if c is None:
        sys.exit(f"모르는 과목 키: {a.course} (있는 것: {', '.join(prof['courseOrder'])})")

    files = [str(Path(f).resolve()) for f in a.files if Path(f).is_file()]
    if not files:
        sys.exit("읽을 파일이 없습니다.")
    if a.syllabus:
        c.setdefault("syllabus", [])
        c["syllabus"] = sorted(set(c["syllabus"]) | set(files))
        print(f"[{a.course}] 강의계획서 {len(files)}개 등록")
    elif a.recording:
        c.setdefault("recordings", {}).setdefault(str(a.week), [])
        c["recordings"][str(a.week)] = sorted(
            set(c["recordings"][str(a.week)]) | set(files))
        print(f"[{a.course}] {a.week}주차 녹음 {len(files)}개 등록")
    else:
        if not a.week:
            sys.exit("--week 를 지정하거나 --syllabus 를 쓰세요.")
        c.setdefault("local", {}).setdefault(str(a.week), [])
        c["local"][str(a.week)] = sorted(set(c["local"][str(a.week)]) | set(files))
        print(f"[{a.course}] {a.week}주차 자료 {len(files)}개 등록")
    P.save(ws.profile_path(pid), prof)
    for f in files:
        print("  " + Path(f).name)
    print("\n다음: semester-board generate")


# ── generate ─────────────────────────────────────────────────────
def cmd_generate(a):
    from .generate import cards
    from .generate.llm import LLM, LLMUnavailable

    ws = _ws(a)
    pid = _pid(a, ws)
    path = ws.profile_path(pid)
    prof = P.load(path)
    nw = prof["semester"].get("weeks", 16)
    llm = LLM(model=a.model, effort=a.effort, dry_run=a.dry_run,
              backend=a.backend)
    if not a.dry_run:
        print(f"백엔드: {llm.backend} · 모델: {llm.model}")
    cache = Cache(ws.cache)
    keys = [a.course] if a.course else list(prof["courseOrder"])

    for k in keys:
        c = prof["courses"][k]
        print(f"\n[{k}] {c['name']}")

        if c.get("syllabus") and (a.all or not c.get("grading")):
            print("  강의계획서 → 과목 뼈대")
            try:
                plan, _ = cards.plan_course(llm, cache, k, c["name"], c["syllabus"], nw)
                if plan:
                    cards.merge_course(c, plan, nw)
                    print(f"    평가 {len(c.get('grading') or [])}항목 · "
                          f"주차 {len(c.get('weeks') or [])} · 마감 {len(c.get('tasks') or [])}")
            except LLMUnavailable as e:
                print(f"    건너뜀 — {e}")

        for wk, files in sorted((c.get("local") or {}).items(), key=lambda x: int(x[0])):
            w = int(wk)
            cur = next((x for x in c.get("weeks") or [] if x["w"] == w), None)
            if cur and cur.get("src") == "m" and not a.all:
                continue
            print(f"  {w}주차 자료 → 카드")
            try:
                card, _ = cards.write_week(llm, cache, c["name"], w, files,
                                           (cur or {}).get("t", ""))
                if card:
                    cards.merge_week(c, w, card)
                    print(f"    {card['t'][:44]} · 항목 {len(card['pts'])}개")
            except LLMUnavailable as e:
                print(f"    건너뜀 — {e}")

        for wk, files in sorted((c.get("recordings") or {}).items(), key=lambda x: int(x[0])):
            w = int(wk)
            tgt = next((x for x in c.get("weeks") or [] if x["w"] == w), None)
            if tgt is None:
                print(f"  {w}주차 녹음 — 해당 주차 카드가 없어 건너뜁니다")
                continue
            if tgt.get("emph") and not a.all:
                continue
            print(f"  {w}주차 녹음 → 강조 블록")
            try:
                emph, _ = cards.add_emphasis(llm, cache, c["name"], w, files,
                                             (c.get("local") or {}).get(wk, []))
                if emph and (emph.get("hi") or emph.get("lo")):
                    tgt["emph"] = {"src": "강의 녹음", "hi": emph.get("hi", []),
                                   "lo": emph.get("lo", [])}
                    print(f"    강조 {len(emph.get('hi') or [])}개 · "
                          f"덜어준 말 {len(emph.get('lo') or [])}개")
            except LLMUnavailable as e:
                print(f"    건너뜀 — {e}")
        P.save(path, prof)

    if a.concepts and not a.course:
        print("\n[전 과목] 겹치는 개념 찾기")
        try:
            got = cards.find_concepts(llm, cache, prof)
            if got and got.get("concepts"):
                prof["concepts"] = got["concepts"]
                print(f"  개념 {len(got['concepts'])}개")
        except LLMUnavailable as e:
            print(f"  건너뜀 — {e}")
        P.save(path, prof)

    print("\n" + llm.report())
    print(P.stats(prof))


# ── build / serve ────────────────────────────────────────────────
def cmd_build(a):
    ws, pid, prof, lms = _load(a)
    err, warn = P.validate(prof)
    for w in warn:
        print("경고: " + w)
    if err:
        for e in err:
            print("오류: " + e)
        sys.exit("프로필을 고친 뒤 다시 빌드하세요.")
    out = Path(a.out) if a.out else ws.build / "dashboard.html"
    p = render.write(out, prof, lms, fragment=a.fragment)
    print(f"{p}  ({p.stat().st_size / 1024:.1f} KB)")
    if lms is None:
        print("(LMS 자료 없이 빌드했습니다 — `semester-board pull` 을 먼저 하면 "
              "영상·출석·자료 링크가 붙습니다.)")


def cmd_serve(a):
    from .serve import serve
    ws, pid, prof, lms = _load(a)
    out = ws.build / "dashboard.html"
    render.write(out, prof, lms)
    serve(out, a.port, not a.no_open)


# ── doctor ───────────────────────────────────────────────────────
def cmd_doctor(a):
    ws = _ws(a)
    print(f"작업 폴더 : {ws.root}")
    print(f"토큰 파일 : {token_file()}  ({'있음' if token_file().exists() else '없음'})")
    profs = sorted(p.stem for p in ws.profiles.glob("*.json")
                   if not p.stem.endswith(".lms"))
    print(f"프로필    : {', '.join(profs) if profs else '없음'}")

    if profs:
        pid = a.profile or profs[0]
        prof = P.load(ws.profile_path(pid))
        print(f"\n[{pid}] {P.stats(prof)}")
        err, warn = P.validate(prof)
        for e in err:
            print("  오류: " + e)
        for w in warn:
            print("  경고: " + w)
        if not err and not warn:
            print("  이상 없음")
        school = load_school(prof.get("school", {}).get("id") or "generic")
        print(f"\nLMS 연결 확인: {school['canvas']}")
        try:
            from .sources.canvas import Canvas
            me = Canvas(school["canvas"]).whoami()
            print(f"  정상 — {me.get('name') or me.get('id')} 로 로그인됩니다.")
        except CanvasError as e:
            print("  " + describe_error(e))


# ── 파서 ─────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="semester-board",
        description="LMS 와 강의자료로 한 장짜리 학기 상황판을 만든다.")
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("-C", "--dir", default=".", help="작업 폴더 (기본: 현재 폴더)")
    ap.add_argument("-p", "--profile", help="프로필 이름 (여러 개일 때)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login", help="LMS 액세스 토큰 저장")
    s.add_argument("--show", action="store_true", help="저장 위치만 확인")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("init", help="새 학기 프로필 만들기")
    s.add_argument("--school", default="ku", help=f"학교 ({', '.join(list_schools())})")
    s.add_argument("--label", default="이번 학기", help="학기 이름 (예: 2026-2학기)")
    s.add_argument("--id", help="프로필 이름")
    s.add_argument("--week1", help="1주차 월요일 YYYY-MM-DD (생략하면 LMS 에서 추론)")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("pull", help="LMS 에서 과목·자료·영상·출석 가져오기")
    s.add_argument("--fix-week1", action="store_true", help="1주차를 LMS 기준으로 교정")
    s.set_defaults(fn=cmd_pull)

    s = sub.add_parser("ingest", help="내 PC 의 강의자료를 과목·주차에 등록")
    s.add_argument("course", help="과목 키")
    s.add_argument("files", nargs="+")
    s.add_argument("-w", "--week", type=int)
    s.add_argument("--syllabus", action="store_true", help="강의계획서로 등록")
    s.add_argument("--recording", action="store_true", help="강의 녹음/전사로 등록")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("generate", help="등록한 자료를 읽어 주차 내용 생성 (모델 호출)")
    s.add_argument("-c", "--course", help="한 과목만")
    s.add_argument("--all", action="store_true", help="이미 만든 것도 다시 생성")
    s.add_argument("--concepts", action="store_true", help="과목 간 겹치는 개념도 찾기")
    s.add_argument("--model", default="claude-opus-5")
    s.add_argument("--effort", default="high",
                   choices=["low", "medium", "high", "xhigh", "max"])
    s.add_argument("--backend", choices=["api", "claude-cli"],
                   help="api=anthropic SDK(키 필요) · claude-cli=설치된 claude 명령")
    s.add_argument("--dry-run", action="store_true", help="호출 없이 대상만 보기")
    s.set_defaults(fn=cmd_generate)

    s = sub.add_parser("build", help="상황판 HTML 만들기")
    s.add_argument("-o", "--out")
    s.add_argument("--fragment", action="store_true",
                   help="<head> 없는 조각으로 (claude.ai 아티팩트용)")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("serve", help="빌드하고 브라우저로 열기")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("doctor", help="설정·토큰·프로필 점검")
    s.set_defaults(fn=cmd_doctor)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        print("\n중단했습니다.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
