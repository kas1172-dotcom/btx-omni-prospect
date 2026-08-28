"""Server-side Gemini synthesis over an already-governed deterministic answer."""
from __future__ import annotations

from typing import Protocol

from google import genai
from google.genai import types
from google.genai.errors import APIError

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import GroundedSynthesisRequest, LanguageResult


class _Models(Protocol):
    def generate_content(self, *, model: str, contents: str, config: object) -> object: ...


class _Client(Protocol):
    models: _Models

    def close(self) -> None: ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, config: AiConfig, client: _Client | None = None) -> None:
        self.config = config
        self._client = client

    @property
    def configured(self) -> bool:
        if self.config.mode.casefold() == "vertex":
            return bool(self.config.project)
        return bool(self.config.api_key)

    def _build_client(self) -> _Client:
        options = types.HttpOptions(
            api_version="v1", timeout=int(self.config.timeout_seconds * 1000)
        )
        if self.config.mode.casefold() == "vertex":
            return genai.Client(
                vertexai=True,
                project=self.config.project,
                location=self.config.location,
                http_options=options,
            )
        return genai.Client(api_key=self.config.api_key, http_options=options)

    def synthesize(self, request: GroundedSynthesisRequest) -> LanguageResult:
        if not self.configured:
            raise RuntimeError("Gemini is not configured.")
        client = self._client or self._build_client()
        prompt = (
            "Rewrite the governed answer below into concise, natural seller-facing language. "
            "Use only facts in GOVERNED ANSWER. Preserve uncertainty, SAMPLE labels, missingness, "
            "and source boundaries. Never claim a write occurred and never add evidence.\n\n"
            f"QUESTION: {request.question}\n\nGOVERNED ANSWER:\n{request.governed_answer}\n\n"
            f"MISSINGNESS:\n{' | '.join(request.missingness) or 'None'}"
        )
        try:
            try:
                response = client.models.generate_content(
                    model=self.config.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=800),
                )
            except (APIError, TimeoutError) as error:
                raise RuntimeError("Gemini is temporarily unavailable.") from error
            content = getattr(response, "text", None)
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Gemini returned no usable content.")
            return LanguageResult(
                content.strip(), self.name, self.config.model, request.evidence_ids
            )
        finally:
            if self._client is None:
                client.close()
