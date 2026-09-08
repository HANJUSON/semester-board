# -*- coding: utf-8 -*-
"""Claude 호출부 — 두 갈래.

api        : anthropic SDK. structured output 으로 스키마를 서버가 강제한다.
claude-cli : 이미 깔려 있는 `claude` 명령을 헤드리스로 부른다. API 키가 없어도
             구독만 있으면 돌아간다. 대신 스키마 강제가 없어 프롬프트로 요구하고
             받은 뒤에 직접 검사한다.

키가 없는 학생이 훨씬 많으므로 둘 다 지원하고, 되는 쪽을 자동으로 고른다.
"""
import json
import os
import re
import shutil
import subprocess

DEFAULT_MODEL = "claude-opus-5"
FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.M)


class LLMUnavailable(Exception):
    pass


def detect_backend() -> str:
    try:
        import anthropic  # noqa: F401
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return "api"
    except ImportError:
        pass
    if shutil.which("claude"):
        return "claude-cli"
    return "api"


def _loads(text: str, schema: dict):
    """모델이 돌려준 글에서 JSON 하나를 꺼내 스키마 필수 항목을 확인한다."""
    s = FENCE.sub("", text.strip())
    if not s.startswith("{"):
        i, j = s.find("{"), s.rfind("}")
        if i < 0 or j < i:
            raise LLMUnavailable(f"JSON 을 찾지 못했습니다: {text[:200]}")
        s = s[i:j + 1]
    try:
        out = json.loads(s)
    except json.JSONDecodeError as e:
        raise LLMUnavailable(f"JSON 파싱 실패: {e}\n{s[:300]}")
    missing = [k for k in (schema.get("required") or []) if k not in out]
    if missing:
        raise LLMUnavailable(f"응답에 빠진 항목: {missing}")
    return out


class LLM:
    def __init__(self, model=DEFAULT_MODEL, effort="high", dry_run=False, backend=None):
        self.model = model
        self.effort = effort
        self.dry_run = dry_run
        self.backend = backend or detect_backend()
        self._client = None
        self.calls = 0
        self.usage = {"input": 0, "output": 0, "cache_read": 0, "usd": 0.0}

    # ── anthropic SDK ────────────────────────────────────────────
    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise LLMUnavailable("anthropic 패키지가 없습니다.  pip install anthropic")
            try:
                self._client = anthropic.Anthropic()
            except Exception as e:
                raise LLMUnavailable(
                    f"Anthropic 클라이언트를 만들지 못했습니다: {e}\n"
                    "ANTHROPIC_API_KEY 를 설정하거나 --backend claude-cli 를 쓰세요.")
        return self._client

    def _via_api(self, system, user, schema, cache_long_input, max_tokens):
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": schema}},
        )
        if cache_long_input:
            kwargs["cache_control"] = {"type": "ephemeral"}
        resp = self.client.messages.create(**kwargs)
        u = resp.usage
        self.usage["input"] += u.input_tokens or 0
        self.usage["output"] += u.output_tokens or 0
        self.usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        if resp.stop_reason == "refusal":
            raise LLMUnavailable(f"모델이 응답을 거절했습니다: {resp.stop_details}")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if not text:
            raise LLMUnavailable("모델이 빈 응답을 돌려줬습니다.")
        return _loads(text, schema)

    # ── claude CLI ───────────────────────────────────────────────
    def _via_cli(self, system, user, schema, timeout=900):
        if not shutil.which("claude"):
            raise LLMUnavailable("`claude` 명령을 찾지 못했습니다.")
        sys_prompt = (system + "\n\n출력 규칙: 아래 JSON 스키마에 정확히 맞는 JSON "
                      "객체 하나만 출력한다. 설명·머리말·코드펜스를 붙이지 않는다.\n"
                      + json.dumps(schema, ensure_ascii=False))
        cmd = ["claude", "-p", "--model", self.model, "--tools", "",
               "--append-system-prompt", sys_prompt, "--output-format", "json"]
        try:
            r = subprocess.run(cmd, input=user, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            raise LLMUnavailable(f"claude 호출이 {timeout}초를 넘겨 중단했습니다.")
        if r.returncode != 0:
            raise LLMUnavailable(f"claude 실패 (코드 {r.returncode}): {r.stderr[:300]}")
        try:
            env = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise LLMUnavailable(f"claude 출력이 JSON 이 아닙니다: {r.stdout[:300]}")
        if env.get("is_error"):
            raise LLMUnavailable(f"claude 오류: {env.get('result', '')[:300]}")
        u = env.get("usage") or {}
        self.usage["input"] += u.get("input_tokens") or 0
        self.usage["output"] += u.get("output_tokens") or 0
        self.usage["cache_read"] += u.get("cache_read_input_tokens") or 0
        self.usage["usd"] += env.get("total_cost_usd") or 0.0
        return _loads(env.get("result") or "", schema)

    # ── 공용 ─────────────────────────────────────────────────────
    def json(self, system, user, schema, cache_long_input=False, max_tokens=16000):
        if self.dry_run:
            raise LLMUnavailable("--dry-run 이라 모델을 호출하지 않았습니다.")
        out = (self._via_cli(system, user, schema) if self.backend == "claude-cli"
               else self._via_api(system, user, schema, cache_long_input, max_tokens))
        self.calls += 1
        return out

    def report(self) -> str:
        u = self.usage
        s = (f"[{self.backend}] 호출 {self.calls}회 · 입력 {u['input']:,} 토큰"
             f"(캐시 {u['cache_read']:,}) · 출력 {u['output']:,} 토큰")
        return s + (f" · ${u['usd']:.2f}" if u["usd"] else "")
