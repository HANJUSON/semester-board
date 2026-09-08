"""프로필 + LMS + 템플릿 → 한 장짜리 상황판 HTML.

템플릿 자체는 <head> 없는 조각이다 — claude.ai 아티팩트로 올릴 때는 호스트가
문서 껍데기를 씌워 주기 때문이다. 로컬 CLI 는 파일을 그냥 더블클릭해서 열게
되므로 여기서 직접 껍데기를 씌운다. charset 이 없으면 한글이 통째로 깨진다.
"""
import json
import re
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "templates" / "dashboard.html"

MARK = {
    "PROFILE": re.compile(r"/\*<<PROFILE>>\*/.*?/\*<</PROFILE>>\*/", re.S),
    "LMS": re.compile(r"/\*<<LMS>>\*/.*?/\*<</LMS>>\*/", re.S),
}
EMPTY_LMS = {"courses": {}, "mods": {}, "vids": [], "att": [], "files": [],
             "asg": [], "done": [], "status": {}, "asof": ""}


SHELL = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
%(title)s
<style>
:root{color-scheme:light dark}
body{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:#faf9f8}
img{max-width:100%%}
[hidden]{display:none!important}
</style>
</head>
<body>
%(body)s
</body>
</html>
"""

TITLE_RE = re.compile(r"<title>(.*?)</title>\s*", re.S)


def wrap(fragment: str) -> str:
    """조각을 통짜 HTML 문서로 감싼다 (제목은 <head> 로 옮긴다)."""
    m = TITLE_RE.search(fragment)
    title = f"<title>{m.group(1)}</title>" if m else "<title>학기 상황판</title>"
    body = TITLE_RE.sub("", fragment, count=1) if m else fragment
    return SHELL % {"title": title, "body": body}


def build(profile: dict, lms: dict = None, template=None, fragment=False) -> str:
    html = Path(template or TEMPLATE).read_text(encoding="utf-8")
    for name, blob in (("PROFILE", profile), ("LMS", lms or EMPTY_LMS)):
        js = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
        # </script> 가 데이터 안에 있으면 문서가 거기서 끊긴다
        js = js.replace("</", "<\\/")
        repl = f"/*<<{name}>>*/{js}/*<</{name}>>*/"
        html, n = MARK[name].subn(lambda _m, r=repl: r, html, count=1)
        if not n:
            raise SystemExit(f"템플릿에서 {name} 주입 지점을 찾지 못했습니다.")
    return html if fragment else wrap(html)


def write(out_path, profile, lms=None, template=None, fragment=False) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build(profile, lms, template, fragment), encoding="utf-8")
    return p
