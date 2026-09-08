"""LearningX(모바일/영상 플랫폼) 클라이언트.

Canvas 는 '영상이 있다'까지만 알려주고, 그 영상을 봤는지 · 출석에 반영되는지 ·
언제까지 봐야 하는지는 LearningX 쪽에만 있다. 붙는 경로는 Canvas 의
sessionless_launch(LTI) 를 태워 세션 쿠키를 받고, 프런트엔드와 똑같이
xn_api_token 쿠키를 Bearer 로 다시 보내는 것이다.
"""
import html as htmlmod
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

from .canvas import UA

DATE_TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}$")   # 대면 수업 출석 항목 (영상 아님)


class LearningX:
    def __init__(self, canvas, host, tool_id=2):
        self.canvas = canvas
        self.host = host.rstrip("/")
        self.api = self.host + "/learningx/api/v1"
        self.tool_id = tool_id

    def _launch(self, cid, external_url):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        url = self.canvas.sessionless_launch(cid, external_url, self.tool_id)
        with op.open(url, timeout=40) as r:
            page = r.read().decode("utf-8", "replace")
        m = re.search(r'<form[^>]*\baction="([^"]+)"[^>]*>(.*?)</form>', page, re.S | re.I)
        if not m:
            raise RuntimeError("LTI 폼을 찾지 못했습니다 (세션 또는 토큰 문제)")
        fields = {}
        for tag in re.findall(r"<input\b[^>]*>", m.group(2), re.I):
            n = re.search(r'\bname="([^"]*)"', tag)
            v = re.search(r'\bvalue="([^"]*)"', tag)
            if n:
                fields[htmlmod.unescape(n.group(1))] = \
                    htmlmod.unescape(v.group(1)) if v else ""
        op.open(urllib.request.Request(
            htmlmod.unescape(m.group(1)),
            data=urllib.parse.urlencode(fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": self.canvas.base.rsplit("/api", 1)[0] + "/"}),
            timeout=40).read()
        return op, cj

    def _get(self, op, cj, path):
        tok = next((c.value for c in cj if c.name == "xn_api_token"), "")
        req = urllib.request.Request(self.api + path, headers={
            "Accept": "application/json", "User-Agent": UA,
            "Referer": self.host + "/learningx/", "Authorization": "Bearer " + tok})
        with op.open(req, timeout=40) as r:
            return json.load(r)

    def fetch(self, cid, items):
        """한 과목의 {요약, 영상 메타}. items 는 canvas 모듈에서 뽑은 출석 항목들."""
        op, cj = self._launch(cid, items[0]["external_url"])
        summaries = (self._get(op, cj, f"/courses/{cid}/attendance_items/summary")
                     or {}).get("attendance_summaries") or {}
        meta = {}
        for mod in self._get(op, cj, f"/courses/{cid}/modules") or []:
            for it in mod.get("module_items") or []:
                cd = it.get("content_data")
                if it.get("content_type") != "attendance_item" or not cd:
                    continue
                if DATE_TITLE.match(it.get("title") or ""):
                    continue
                icd = cd.get("item_content_data") or {}
                meta[str(it["module_item_id"])] = {
                    "a": 1 if cd.get("use_attendance") else 0,
                    "due": (cd.get("due_at") or "")[:10],
                    "sec": int(icd.get("duration") or 0)}
        return summaries, meta


def attendance_items(modules, week_re):
    """Canvas 모듈 덤프에서 출석/영상 항목을 뽑는다."""
    out = []
    for mod in modules:
        m = week_re.search(mod.get("name") or "")
        wk = int(m.group(1)) if m else None
        for it in (mod.get("items") or []):
            ext = it.get("external_url") or ""
            if it.get("type") == "ExternalTool" and "lecture_attendance" in ext:
                out.append({"canvas_item": it["id"],
                            "lx_item": ext.rstrip("/").split("/")[-1],
                            "title": it["title"],
                            "week": wk,
                            "external_url": ext,
                            "is_video": not DATE_TITLE.match(it["title"])})
    return out
