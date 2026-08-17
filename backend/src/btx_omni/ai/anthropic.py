"""Thin Anthropic implementation. Calls are made only by explicit AI assistance paths."""
from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import AiRequest, AiResult


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def _ask(self, request: AiRequest) -> AiResult:
        if not self.config.anthropic_api_key:
            raise RuntimeError("Anthropic is unavailable: ANTHROPIC_API_KEY is not configured")
        body = json.dumps({"model": self.config.anthropic_model, "max_tokens": 800, "messages": [{"role": "user", "content": f"{request.instruction}\n\n{request.text}"}]}).encode()
        http_request = Request("https://api.anthropic.com/v1/messages", data=body, headers={"x-api-key": self.config.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, method="POST")
        try:
            with urlopen(http_request, timeout=30) as response:  # nosec B310: fixed vendor endpoint
                payload = json.loads(response.read())
        except HTTPError as exc:
            raise RuntimeError(f"Anthropic request failed: HTTP_{exc.code}") from exc
        content = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        return AiResult(content, self.name, self.config.anthropic_model, request.evidence_ids)

    def extract_structured_event(self, request: AiRequest) -> AiResult: return self._ask(request)
    def classify_event(self, request: AiRequest) -> AiResult: return self._ask(request)
    def resolve_ambiguity(self, request: AiRequest) -> AiResult: return self._ask(request)
    def summarize_evidence(self, request: AiRequest) -> AiResult: return self._ask(request)
    def assist_entity_resolution(self, request: AiRequest) -> AiResult: return self._ask(request)
