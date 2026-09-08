"""파일이 놓이는 자리.

토큰은 작업 폴더가 아니라 사용자 설정 폴더에 둔다. 작업 폴더를 통째로
git 에 올리는 실수가 잦기 때문이다.
"""
import os
from pathlib import Path

APP = "semester-board"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    d = Path(base) / APP
    d.mkdir(parents=True, exist_ok=True)
    return d


def token_file() -> Path:
    return config_dir() / "token"


class Workspace:
    """현재 작업 폴더. profiles/ cache/ build/ 세 갈래만 쓴다."""

    def __init__(self, root=None):
        self.root = Path(root or os.getcwd()).resolve()

    @property
    def profiles(self) -> Path:
        return self.root / "profiles"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def build(self) -> Path:
        return self.root / "build"

    def profile_path(self, pid: str) -> Path:
        return self.profiles / f"{pid}.json"

    def lms_path(self, pid: str) -> Path:
        return self.profiles / f"{pid}.lms.json"

    def ensure(self):
        for d in (self.profiles, self.cache, self.build):
            d.mkdir(parents=True, exist_ok=True)
        return self
