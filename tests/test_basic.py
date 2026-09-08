"""외부 의존성·네트워크·모델 호출 없이 도는 검사."""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from semester_board import profile as P, render, week as W       # noqa: E402
from semester_board.generate import prompts                       # noqa: E402
from semester_board.ingest.cache import Cache                     # noqa: E402
from semester_board.ingest.extract import extract                 # noqa: E402

SAMPLE = ROOT / "examples" / "profile.sample.json"


def test_week1_inference():
    """주차와 날짜 쌍에서 1주차 월요일을 역산한다."""
    pairs = [(2, datetime.date(2026, 9, 9)), (3, datetime.date(2026, 9, 16)),
             (16, datetime.date(2026, 12, 16))]
    assert W.infer_week1(pairs) == datetime.date(2026, 8, 31)


def test_week1_inference_refuses_when_split():
    """근거가 갈리면 임의로 고르지 않는다."""
    assert W.infer_week1([(1, datetime.date(2026, 3, 2)),
                          (1, datetime.date(2026, 3, 9))]) is None


def test_week_math_roundtrip():
    w1 = datetime.date(2026, 8, 31)
    for n in range(1, 17):
        assert W.week_of(w1, W.week_start(w1, n)) == n
        assert W.week_of(w1, W.week_end(w1, n)) == n


def test_sample_profile_is_valid():
    prof = json.loads(SAMPLE.read_text(encoding="utf-8"))
    err, _ = P.validate(prof)
    assert err == [], err


def test_validate_catches_bad_week1():
    prof = json.loads(SAMPLE.read_text(encoding="utf-8"))
    prof["semester"]["week1Monday"] = "2026-03-03"      # 화요일
    _, warn = P.validate(prof)
    assert any("월요일이 아닙니다" in w for w in warn)


def test_validate_catches_missing_course():
    prof = json.loads(SAMPLE.read_text(encoding="utf-8"))
    prof["courseOrder"].append("nope")
    err, _ = P.validate(prof)
    assert any("nope" in e for e in err)


def test_render_injects_and_wraps():
    prof = json.loads(SAMPLE.read_text(encoding="utf-8"))
    html = render.build(prof, None)
    assert html.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in html          # 없으면 한글이 깨진다
    assert "<title>" in html.split("</head>")[0]
    assert '"알고리즘"' in html
    assert "/*<<PROFILE>>*/" in html and "/*<</LMS>>*/" in html


def test_render_fragment_has_no_shell():
    prof = json.loads(SAMPLE.read_text(encoding="utf-8"))
    frag = render.build(prof, None, fragment=True)
    assert not frag.startswith("<!doctype")


def test_render_escapes_script_close():
    """데이터에 </script> 가 있어도 문서가 끊기지 않아야 한다."""
    prof = json.loads(SAMPLE.read_text(encoding="utf-8"))
    prof["courses"]["algo"]["note"] = "위험: </script><b>주입</b>"
    html = render.build(prof, None)
    assert "</script><b>주입" not in html
    assert html.count("<script>") == html.count("</script>")


def test_template_keeps_helper_functions():
    """데이터를 걷어낼 때 로직까지 잘려나간 적이 있다."""
    tpl = render.TEMPLATE.read_text(encoding="utf-8")
    for fn in ("courseId", "modURL", "curWeek", "emphHTML", "matHTML"):
        assert f"function {fn}" in tpl, fn


def test_cache_key_follows_content(tmp_path):
    c = Cache(tmp_path)
    k = Cache.key("t", "abc")
    assert c.get(k) is None
    c.put(k, {"v": 1})
    assert c.get(k) == {"v": 1}
    assert Cache.key("t", "abc") == k
    assert Cache.key("t", "abd") != k


def test_extract_text_and_subtitles(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("안녕", encoding="utf-8")
    assert extract(p) == "안녕"

    v = tmp_path / "b.vtt"
    v.write_text("WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\n첫 줄\n첫 줄\n두 줄\n",
                 encoding="utf-8")
    assert extract(v).splitlines() == ["첫 줄", "두 줄"]


def test_prompt_schemas_are_strict():
    """구조화 출력은 required 가 빠지거나 additionalProperties 가 열리면 깨진다."""
    def check(node, path="root"):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, path
            props = set(node.get("properties") or {})
            assert set(node.get("required") or []) == props, path
            for n, v in (node.get("properties") or {}).items():
                check(v, f"{path}.{n}")
        if node.get("type") == "array":
            check(node.get("items") or {}, path + "[]")

    for name in ("COURSE_SCHEMA", "WEEK_SCHEMA", "EMPH_SCHEMA", "CONCEPT_SCHEMA"):
        check(getattr(prompts, name), name)


if __name__ == "__main__":
    fails = 0
    import tempfile
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            if "tmp_path" in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"  통과  {name}")
        except AssertionError as e:
            fails += 1
            print(f"  실패  {name}: {e}")
    print(f"\n{'모두 통과' if not fails else f'{fails}개 실패'}")
    sys.exit(1 if fails else 0)
