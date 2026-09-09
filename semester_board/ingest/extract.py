"""강의자료에서 글자를 뽑는다.

원문 파일은 이 도구 밖으로 나가지 않는다 — 여기서 텍스트로 바꾸고,
필요한 만큼만 모델에 보낸다. 외부 의존성은 최대한 피했다.
pptx·docx·hwpx 는 사실 zip 안의 XML 이라 표준 라이브러리로 충분하다.
"""
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".csv", ".json"}
CUE = re.compile(r"^\s*(\d+\s*$|[\d:.,]+\s*-->\s*[\d:.,]+)")


class Unsupported(Exception):
    pass


def extract(path) -> str:
    p = Path(path)
    if not p.exists():
        raise Unsupported(f"파일이 없습니다: {p}")
    ext = p.suffix.lower()
    if ext in TEXT_EXT:
        return p.read_text(encoding="utf-8", errors="replace")
    if ext in (".vtt", ".srt"):
        return _subtitle(p)
    if ext == ".pdf":
        return _pdf(p)
    if ext in (".pptx", ".docx", ".hwpx"):
        return _ooxml(p, ext)
    if ext in (".hwp", ".ppt", ".doc"):
        return _legacy(p, ext)
    raise Unsupported(f"지원하지 않는 형식입니다: {ext}")


def _subtitle(p: Path) -> str:
    """자막에서 말만 남긴다 (번호·타임코드 제거, 연속 중복 줄 제거)."""
    out, prev = [], None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s == "WEBVTT" or CUE.match(s):
            continue
        s = re.sub(r"<[^>]+>", "", s)
        if s != prev:
            out.append(s)
            prev = s
    return "\n".join(out)


def _pdf(p: Path) -> str:
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(p), "-"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    try:
        from pypdf import PdfReader
    except ImportError:
        raise Unsupported(
            f"{p.name}: PDF 를 읽으려면 poppler-utils(pdftotext) 또는 pypdf 가 필요합니다.\n"
            "  sudo apt install poppler-utils   또는   pip install pypdf")
    return "\n\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)


def _ooxml(p: Path, ext: str) -> str:
    """pptx/docx/hwpx 는 zip 속 XML 이다. 문단 단위로 텍스트 노드를 긁는다.

    태그 이름 뒤에 공백이나 '>' 가 오도록 반드시 막아야 한다. <w:t[^>]*> 로
    쓰면 <w:tbl> · <w:tc> · <w:tr> 까지 함께 매치돼서, 표가 있는 문서는 본문
    대신 XML 마크업이 통째로 딸려 나온다(강의계획서 docx 실측 45배).

    한 문단의 텍스트 조각(run)은 문장 중간에서 갈리므로 공백을 지우지 않고
    이어 붙이고, 줄 단위로만 정리한다.
    """
    want = {".pptx": "ppt/slides/slide", ".docx": "word/document",
            ".hwpx": "Contents/section"}[ext]
    tag = {".pptx": "a:t", ".docx": "w:t", ".hwpx": "hp:t"}[ext]
    para = {".pptx": "a:p", ".docx": "w:p", ".hwpx": "hp:p"}[ext]
    text_re = re.compile(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", re.S)
    para_re = re.compile(rf"</{para}\s*>")

    chunks = []
    with zipfile.ZipFile(p) as z:
        names = sorted((n for n in z.namelist() if n.startswith(want) and n.endswith(".xml")),
                       key=_natural)
        for n in names:
            xml = z.read(n).decode("utf-8", "replace")
            lines = []
            for para_xml in para_re.split(xml):          # 문단 하나가 곧 한 줄
                line = "".join(_unescape(t) for t in text_re.findall(para_xml)).strip()
                if line:
                    lines.append(line)
            if lines:
                label = f"\n--- {Path(n).stem} ---\n" if ext == ".pptx" else "\n"
                chunks.append(label + "\n".join(lines))
    if not chunks:
        raise Unsupported(f"{p.name}: 글자를 찾지 못했습니다 (이미지 기반 문서일 수 있습니다).")
    return "\n".join(chunks)


def _legacy(p: Path, ext: str) -> str:
    """hwp/ppt/doc — 외부 변환기가 있으면 쓰고, 없으면 방법을 알려준다."""
    if ext == ".hwp" and shutil.which("hwp5txt"):
        r = subprocess.run(["hwp5txt", str(p)], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    if shutil.which("libreoffice") or shutil.which("soffice"):
        raise Unsupported(
            f"{p.name}: 아래로 변환한 뒤 다시 넣어 주세요.\n"
            f"  libreoffice --headless --convert-to pdf '{p}'")
    raise Unsupported(
        f"{p.name}: {ext} 는 바로 읽지 못합니다. PDF 로 저장한 뒤 넣어 주세요."
        + ("\n  (pip install pyhwp 를 설치하면 hwp 를 직접 읽습니다)" if ext == ".hwp" else ""))


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _unescape(s: str) -> str:
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&apos;", "'"), ("&amp;", "&")):
        s = s.replace(a, b)
    return s


def page_count(path) -> int | None:
    p = Path(path)
    if p.suffix.lower() == ".pdf" and shutil.which("pdfinfo"):
        r = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True)
        m = re.search(r"^Pages:\s*(\d+)", r.stdout, re.M)
        return int(m.group(1)) if m else None
    return None
