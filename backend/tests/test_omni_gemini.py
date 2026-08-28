from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import GroundedSynthesisRequest, LanguageResult
from btx_omni.ai.gemini import GeminiProvider
from btx_omni.modules.assistant.service import OmniService
from btx_omni.modules.assistant.tools import (
    GovernedReadTools,
    GovernedToolError,
    ToolCall,
)
from btx_omni.providers.sample.environment import build_sample_environment


class FakeModels:
    def __init__(self, text: str | None = "Grounded Gemini synthesis") -> None:
        self.text = text
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


class FakeClient:
    def __init__(self, text: str | None = "Grounded Gemini synthesis") -> None:
        self.models = FakeModels(text)

    def close(self) -> None:
        pass


class FailingProvider:
    name = "gemini"
    configured = True

    def synthesize(self, _request):
        raise TimeoutError("provider timeout detail must not escape")


def config(**overrides) -> AiConfig:
    values = {
        "provider": "gemini",
        "api_key": "test-key",
        "model": "gemini-test",
        "mode": "developer",
        "project": None,
        "location": "global",
        "timeout_seconds": 2,
    }
    values.update(overrides)
    return AiConfig(**values)


def test_gemini_contract_is_grounded_and_traceable_without_live_call() -> None:
    client = FakeClient()
    provider = GeminiProvider(config(), client)
    result = provider.synthesize(
        GroundedSynthesisRequest("Why?", "Canonical answer", ("ev-1",), ("gap",))
    )
    assert result == LanguageResult(
        "Grounded Gemini synthesis", "gemini", "gemini-test", ("ev-1",)
    )
    prompt = client.models.calls[0]["contents"]
    assert "Canonical answer" in prompt and "never add evidence" in prompt


def test_developer_and_vertex_configuration_are_explicit() -> None:
    assert not GeminiProvider(config(api_key=None)).configured
    assert GeminiProvider(config(mode="vertex", api_key=None, project="btx-project")).configured
    assert not GeminiProvider(config(mode="vertex", api_key=None, project=None)).configured


def test_read_tool_registry_rejects_unknown_malformed_and_unbounded_calls() -> None:
    registry = GovernedReadTools(lambda arguments: arguments["question"])
    assert registry.execute((ToolCall("resolve_governed_context", {"question": "x"}),)) == ("x",)
    with pytest.raises(GovernedToolError, match="Unknown"):
        registry.execute((ToolCall("create_action", {"question": "x"}),))
    with pytest.raises(GovernedToolError, match="must be text"):
        registry.execute((ToolCall("resolve_governed_context", {"question": 1}),))
    with pytest.raises(GovernedToolError, match="limit"):
        registry.execute((ToolCall("resolve_governed_context", {"question": "x"}),) * 2)
    assert all(definition.read_only for definition in registry.definitions)


def test_provider_failure_returns_truthful_deterministic_fallback() -> None:
    response = OmniService(FailingProvider()).answer(
        build_sample_environment(),
        account_id="boeing",
        question="Why does this Customer matter?",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "boeing"},
        intelligence_events=(),
        work_items=(),
    )
    assert response.content
    assert response.provider_status == "UNAVAILABLE"
    assert response.language_provider == "deterministic"


def test_configured_provider_synthesizes_but_preserves_governed_metadata() -> None:
    provider = GeminiProvider(config(), FakeClient("Concise governed answer"))
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id="boeing",
        question="Explain the score",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "boeing"},
        intelligence_events=(),
        work_items=(),
    )
    assert response.content == "Concise governed answer"
    assert response.provider_status == "AVAILABLE"
    assert response.language_model == "gemini-test"
    assert response.context_used.get("account_id") == "boeing"
