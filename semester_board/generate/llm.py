"""Claude 호출부.

이 도구에서 모델이 하는 일은 하나다 — 강의자료를 읽고 정해진 모양의 JSON 을
돌려주는 것. 그래서 자유 서술 대신 structured output 으로 못을 박고,
같은 문서를 두 번 보내지 않도록 캐시를 앞에 둔다.
"""
import json
import os

DEFAULT_MODEL = "claude-opus-5"


class LLMUnavailable(Exception):
    pass


class LLM:
    def __init__(self, model=DEFAULT_MODEL, effort="high", dry_run=False):
        self.model = model
        self.effort = effort
        self.dry_run = dry_run
        self._client = None
        self.calls = 0
        self.usage = {"input": 0, "output": 0, "cache_read": 0}

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise LLMUnavailable(
                    "anthropic 패키지가 없습니다.  pip install anthropic")
            if not (os.environ.get("ANTHROPIC_API_KEY")
                    or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                # ant auth login 프로필이 있으면 인자 없는 생성자가 알아서 찾는다
                pass
            try:
                self._client = anthropic.Anthropic()
            except Exception as e:
                raise LLMUnavailable(
                    f"Anthropic 클라이언트를 만들지 못했습니다: {e}\n"
                    "ANTHROPIC_API_KEY 를 설정하거나 `ant auth login` 을 실행하세요.")
        return self._client

    def json(self, system, user, schema, cache_long_input=False, max_tokens=16000):
        """스키마에 맞는 dict 하나를 돌려준다."""
        if self.dry_run:
            raise LLMUnavailable("--dry-run 이라 모델을 호출하지 않았습니다.")
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        if cache_long_input:
            # 같은 강의자료를 여러 주차·여러 작업에서 다시 보낼 때 값이 싸진다
            kwargs["cache_control"] = {"type": "ephemeral"}

        resp = self.client.messages.create(**kwargs)
        self.calls += 1
        u = resp.usage
        self.usage["input"] += u.input_tokens or 0
        self.usage["output"] += u.output_tokens or 0
        self.usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0

        if resp.stop_reason == "refusal":
            raise LLMUnavailable(f"모델이 응답을 거절했습니다: {resp.stop_details}")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if not text:
            raise LLMUnavailable("모델이 빈 응답을 돌려줬습니다.")
        return json.loads(text)

    def report(self) -> str:
        u = self.usage
        return (f"모델 호출 {self.calls}회 · 입력 {u['input']:,} 토큰"
                f"(캐시 {u['cache_read']:,}) · 출력 {u['output']:,} 토큰")
