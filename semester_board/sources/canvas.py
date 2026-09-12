"""Canvas LMS 클라이언트.

이 파일이 존재하는 이유의 절반은 401 이다. Canvas 는 '토큰이 죽었다'와
'이 자원을 볼 권한이 없다'를 똑같이 401 로 돌려준다. 실제로 학생 계정은
대부분의 과목에서 /files 가 401 인데(파일 탭이 꺼져 있다), 이걸 만료로
읽으면 멀쩡한 토큰을 버리게 된다. 그래서 401 을 만나면 반드시
/users/self 로 토큰 자체를 한 번 더 확인하고 종류를 갈라준다.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from ..paths import token_file

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0 Safari/537.36")


class CanvasError(Exception):
    """kind: 'expired'(토큰 만료·무효) | 'forbidden'(권한 없음) | 'http' | 'network'"""

    def __init__(self, msg, kind="http", status=None):
        super().__init__(msg)
        self.kind = kind
        self.status = status


def read_token(explicit=None) -> str:
    """토큰은 인자 → 환경변수 → 설정 파일 순으로 찾는다. 화면에는 절대 찍지 않는다."""
    if explicit:
        return explicit.strip()
    env = os.environ.get("SEMESTER_BOARD_TOKEN")
    if env:
        return env.strip()
    f = token_file()
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    raise CanvasError(
        "액세스 토큰이 없습니다. `semester-board login` 으로 저장하거나 "
        "SEMESTER_BOARD_TOKEN 환경변수를 설정하세요.", kind="expired")


class Canvas:
    def __init__(self, base_url: str, token: str = None):
        self.base = base_url.rstrip("/") + "/api/v1"
        self.token = read_token(token)
        self._self = None

    # ── 저수준 ────────────────────────────────────────────────
    def _open(self, url):
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
            "User-Agent": UA})
        try:
            return urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise CanvasError(_msg_of(e), kind=self._classify_401(), status=e.code)
            raise CanvasError(f"{e.code} {e.reason}", kind="http", status=e.code)
        except urllib.error.URLError as e:
            raise CanvasError(f"연결 실패: {e.reason}", kind="network")

    def _classify_401(self) -> str:
        """토큰이 살아 있으면 'forbidden', 죽었으면 'expired'."""
        if self._self is not None:
            return "forbidden"
        try:
            req = urllib.request.Request(self.base + "/users/self", headers={
                "Authorization": "Bearer " + self.token, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                self._self = json.load(r)
            return "forbidden"
        except Exception:
            return "expired"

    def get(self, path, paginate=True):
        """Link 헤더를 따라가며 전부 모은다."""
        url = self.base + path
        items, first = [], True
        while url:
            with self._open(url) as r:
                data = json.load(r)
                if isinstance(data, list):
                    items.extend(data)
                else:
                    if first and not paginate:
                        return data
                    items.append(data)
                url = None
                if paginate:
                    for part in (r.headers.get("Link") or "").split(","):
                        if 'rel="next"' in part:
                            url = part.split(";")[0].strip().strip("<>")
            first = False
        return items

    def try_get(self, path):
        """권한이 없어 막힌 자원은 조용히 빈 목록으로. 만료는 그대로 올린다."""
        try:
            return self.get(path)
        except CanvasError as e:
            if e.kind == "forbidden":
                return []
            raise

    # ── 고수준 ────────────────────────────────────────────────
    def whoami(self):
        if self._self is None:
            self._self = self.get("/users/self", paginate=False)
        return self._self

    def courses(self):
        return self.get("/courses?enrollment_state=active"
                        "&include[]=teachers&per_page=100")

    def modules(self, cid):
        return self.try_get(f"/courses/{cid}/modules?include[]=items&per_page=100")

    def assignments(self, cid):
        # 제출 상태(submission)까지 함께 받아야 '아직 안 낸 것'을 가릴 수 있다
        return self.try_get(f"/courses/{cid}/assignments"
                            "?per_page=100&include[]=submission")

    def files(self, cid):
        return self.try_get(f"/courses/{cid}/files?per_page=100")

    def sessionless_launch(self, cid, external_url, tool_id):
        q = urllib.parse.quote(external_url, safe="")
        return self.get(f"/courses/{cid}/external_tools/sessionless_launch"
                        f"?id={tool_id}&url={q}", paginate=False)["url"]


def _msg_of(e) -> str:
    try:
        body = json.load(e)
        errs = body.get("errors") or []
        if errs and isinstance(errs, list):
            return errs[0].get("message") or str(body)
        return str(body)
    except Exception:
        return f"{e.code} {e.reason}"
