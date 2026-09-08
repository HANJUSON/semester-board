"""내용 해시 기반 캐시.

같은 파일을 두 번 모델에 보내지 않기 위한 것이다. 강의자료 한 학기치를
매번 다시 넣으면 요금이 그대로 두 배가 된다. 키는 파일 내용 + 작업 이름이라,
파일 이름을 바꾸거나 옮겨도 캐시가 살아 있다.
"""
import hashlib
import json
from pathlib import Path


class Cache:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(task: str, *parts) -> str:
        h = hashlib.sha256()
        h.update(task.encode())
        for p in parts:
            h.update(b"\x00")
            h.update(p if isinstance(p, bytes) else str(p).encode())
        return h.hexdigest()[:32]

    @staticmethod
    def file_key(task: str, path, *extra) -> str:
        data = Path(path).read_bytes()
        return Cache.key(task, hashlib.sha256(data).hexdigest(), *extra)

    def get(self, key):
        f = self.root / f"{key}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def put(self, key, value):
        (self.root / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
        return value
