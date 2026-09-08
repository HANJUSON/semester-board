"""학교 어댑터. 학교마다 다른 것은 코드가 아니라 이 JSON 들이다."""
import json
import re
from pathlib import Path

SCHOOLS_DIR = Path(__file__).resolve().parent / "schools"


def list_schools():
    return sorted(p.stem for p in SCHOOLS_DIR.glob("*.json"))


def load_school(sid: str) -> dict:
    p = SCHOOLS_DIR / f"{sid}.json"
    if not p.exists():
        raise SystemExit(f"모르는 학교입니다: {sid} (가능: {', '.join(list_schools())})")
    return json.loads(p.read_text(encoding="utf-8"))


def week_re(school: dict):
    return re.compile(school.get("weekPattern") or r"(\d+)\s*주차")


def course_title(school: dict, raw: str) -> str:
    """LMS 과목명에서 사람이 읽는 제목만 남긴다."""
    pat = school.get("courseNamePattern")
    if pat:
        m = re.search(pat, raw)
        if m:
            return (m.groupdict().get("title") or m.group(1)).strip()
    return raw.strip()
