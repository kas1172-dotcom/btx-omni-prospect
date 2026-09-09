from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from btx_omni.ai.config import AiConfig
from btx_omni.ai.contracts import (
    CanonicalToolSelectionRequest,
    ConversationTurn,
    GroundedSynthesisRequest,
    IntentInterpretation,
    IntentInterpretationRequest,
    LanguageProviderError,
    LanguageResult,
    ProviderStatus,
    ReadIntent,
)
from btx_omni.ai.gemini import GeminiProvider
from btx_omni.modules.assistant.service import OmniService
from btx_omni.modules.assistant.tools import (
    GovernedReadTools,
    GovernedToolError,
    ToolCall,
)
from btx_omni.persistence.ai_usage import AiUsageRepository, ai_call_receipts
from btx_omni.providers.sample.environment import build_sample_environment


@pytest.mark.parametrize('selected, entity, expected', [
    ('northrop-grumman', 'Northrop', 'northrop-grumman'),
    (None, 'Northrop', ''),
    ('boeing', 'Northrop', ''),
    ('northrop-grumman', 'North', ''),
])
def test_short_name_is_scoped_continuation_not_global_identity_alias(selected, entity, expected):
    from btx_omni.modules.assistant.orchestration import OmniOrchestrator

    response = OmniOrchestrator().answer(
        build_sample_environment(), account_id=selected,
        question=f'Explain {entity} buyer context', observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={'_interpreted_intent': 'ACCOUNT_OVERVIEW', '_interpreted_entity_text': entity},
        intelligence_events=(), work_items=(),
    )
    assert response.account_id == expected
    if not expected:
        assert response.context_used['interpretation_status'] == 'CLARIFICATION'


class FakeModels:
    def __init__(
        self,
        text: str | None = "Grounded Gemini synthesis",
        intent_text: str = '{"intent":"ACCOUNT_OVERVIEW","entity_text":null}',
    ) -> None:
        self.text = text
        self.intent_text = intent_text
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if getattr(kwargs["config"], "response_mime_type", None) == "application/json":
            return SimpleNamespace(text=self.intent_text)
        return SimpleNamespace(text=self.text)


class FakeClient:
    def __init__(
        self,
        text: str | None = "Grounded Gemini synthesis",
        intent_text: str = '{"intent":"ACCOUNT_OVERVIEW","entity_text":null}',
    ) -> None:
        self.models = FakeModels(text, intent_text)

    def close(self) -> None:
        pass


class FailingProvider:
    name = "gemini"
    configured = True

    def synthesize(self, _request):
        raise TimeoutError("provider timeout detail must not escape")


class ClassifiedFailingProvider:
    name = "gemini"
    configured = True

    def __init__(self, status: ProviderStatus) -> None:
        self.status = status

    def synthesize(self, _request):
        raise LanguageProviderError(self.status)


class FakeInterpretingProvider:
    name = "gemini"
    configured = True

    def __init__(
        self,
        interpretation: IntentInterpretation | Exception,
        synthesis: str = "Seller-readable grounded synthesis",
        synthesis_evidence_ids: tuple[str, ...] | None = None,
    ) -> None:
        self.interpretation = interpretation
        self.synthesis = synthesis
        self.synthesis_evidence_ids = synthesis_evidence_ids
        self.interpret_requests: list[IntentInterpretationRequest] = []
        self.synthesis_requests: list[GroundedSynthesisRequest] = []

    def interpret(self, request: IntentInterpretationRequest) -> IntentInterpretation:
        self.interpret_requests.append(request)
        if isinstance(self.interpretation, Exception):
            raise self.interpretation
        return self.interpretation

    def synthesize(self, request: GroundedSynthesisRequest) -> LanguageResult:
        self.synthesis_requests.append(request)
        return LanguageResult(
            self.synthesis,
            self.name,
            "fake-gemini",
            self.synthesis_evidence_ids or request.evidence_ids,
        )


def config(**overrides) -> AiConfig:
    engine = create_engine("sqlite://")
    ai_call_receipts.create(engine)
    values = {
        "provider": "gemini",
        "api_key": "test-key",
        "model": "gemini-test",
        "mode": "developer",
        "project": None,
        "location": "global",
        "timeout_seconds": 2,
        "usage": AiUsageRepository(engine),
    }
    values.update(overrides)
    return AiConfig(**values)


def test_canonical_selector_supplies_closed_tool_specific_schema():
    from btx_omni.modules.assistant.commercial_tools import DEFINITIONS
    client = FakeClient(intent_text='{"tool":"read_fulfillment","arguments":{}}')
    provider = GeminiProvider(config(), client)
    result = provider.choose_canonical_read(CanonicalToolSelectionRequest('Read delivery', 'kla', DEFINITIONS, (), 4))
    assert result == {'tool': 'read_fulfillment', 'arguments': {}}
    schema = client.models.calls[0]['config'].response_json_schema
    assert len(schema['anyOf']) == len(DEFINITIONS) + 1
    for branch, definition in zip(schema['anyOf'][1:], DEFINITIONS, strict=True):
        assert branch['additionalProperties'] is False
        assert branch['properties']['tool']['enum'] == [definition['name']]
        assert branch['properties']['arguments']['required'] == definition['arguments']
        assert branch['properties']['arguments']['additionalProperties'] is False


def test_gemini_contract_is_grounded_and_traceable_without_live_call() -> None:
    client = FakeClient()
    provider = GeminiProvider(config(), client)
    result = provider.synthesize(
        GroundedSynthesisRequest(
            "Why?",
            "Canonical answer",
            ("ev-1",),
            ("gap",),
            (ConversationTurn("user", "Tell me about Boeing."),),
        )
    )
    assert result == LanguageResult(
        "Grounded Gemini synthesis", "gemini", "gemini-test", ("ev-1",)
    )
    prompt = client.models.calls[0]["contents"]
    assert "Canonical answer" in prompt and "never add evidence" in prompt
    assert "USER: Tell me about Boeing." in prompt
    assert "never treat assistant prose as evidence" in prompt


def test_canonical_selector_preserves_server_supplied_argument_enums():
    client = FakeClient(intent_text='{"done":true}')
    provider = GeminiProvider(config(), client)
    tools = ({'name': 'fetch_document', 'arguments': ['source_id'],
              'argument_values': {'source_id': ['primary', 'source:known']}},)
    provider.choose_canonical_read(CanonicalToolSelectionRequest('Investigate', 'PUBLIC_RESEARCH_ONLY', tools, (), 2))
    schema = client.models.calls[0]['config'].response_json_schema
    assert schema['anyOf'][1]['properties']['arguments']['properties']['source_id'] == {
        'type': 'string', 'enum': ['primary', 'source:known']}


def test_developer_and_vertex_configuration_are_explicit() -> None:
    assert not GeminiProvider(config(api_key=None)).configured
    assert GeminiProvider(config(mode="vertex", api_key=None, project="btx-project")).configured
    assert not GeminiProvider(config(mode="vertex", api_key=None, project=None)).configured


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY", "RECITATION"])
def test_incomplete_provider_output_is_not_published_as_success(finish):
    client = FakeClient()
    client.models.generate_content = lambda **kwargs: SimpleNamespace(
        text="A truncated but nonempty answer", candidates=[SimpleNamespace(finish_reason=finish)],
        usage_metadata=SimpleNamespace(prompt_token_count=20, candidates_token_count=5, total_token_count=30, thoughts_token_count=5),
    )
    provider = GeminiProvider(config(), client)
    with pytest.raises(LanguageProviderError) as caught:
        provider.synthesize(GroundedSynthesisRequest("Question", "Canonical answer", (), ()))
    assert caught.value.status == ProviderStatus.UNAVAILABLE
    assert provider.usage_log[0]["finish_reason"] == finish
    assert provider.usage_log[0]["total_tokens"] == 30
    assert "A truncated" not in str(provider.usage_log)


def test_gemini_thinking_configuration_is_model_family_specific():
    from google.genai.types import ThinkingLevel

    assert GeminiProvider(config(model="gemini-3.6-flash"))._read_thinking().thinking_level is ThinkingLevel.LOW
    assert GeminiProvider(config(model="gemini-2.5-flash"))._read_thinking() is None


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
    assert response.provider_status == "TIMEOUT"
    assert response.language_provider == "deterministic"


@pytest.mark.parametrize(
    "provider,status",
    [
        (None, "NOT_CONFIGURED"),
        (ClassifiedFailingProvider(ProviderStatus.AUTH_FAILED), "AUTH_FAILED"),
        (FailingProvider(), "TIMEOUT"),
        (ClassifiedFailingProvider(ProviderStatus.QUOTA), "QUOTA"),
        (ClassifiedFailingProvider(ProviderStatus.UNAVAILABLE), "UNAVAILABLE"),
    ],
)
def test_provider_diagnostics_are_safe_and_fall_back(provider, status: str) -> None:
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id="boeing",
        question="What changed recently?",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={
            "conversation_referent": {"account_id": "boeing", "route": "ACCOUNT"},
            "prior_turns": "user: Tell me about Boeing.\nassistant: untrusted prose",
        },
        intelligence_events=(),
        work_items=(),
    )
    assert response.provider_status == status
    assert response.language_provider == "deterministic"
    assert "provider timeout detail" not in response.content


def test_gemini_api_failures_map_to_bounded_diagnostics() -> None:
    for code, expected in (
        (401, ProviderStatus.AUTH_FAILED),
        (403, ProviderStatus.AUTH_FAILED),
        (408, ProviderStatus.TIMEOUT),
        (429, ProviderStatus.QUOTA),
        (500, ProviderStatus.UNAVAILABLE),
    ):
        assert GeminiProvider._api_error_status(SimpleNamespace(code=code)) is expected


def test_gemini_intent_contract_rejects_disallowed_and_extra_fields() -> None:
    disallowed = GeminiProvider(
        config(), FakeClient(intent_text='{"intent":"CREATE_ACTION","entity_text":"Boeing"}')
    )
    injected = GeminiProvider(
        config(),
        FakeClient(
            intent_text='{"intent":"ACCOUNT_OVERVIEW","entity_text":"Boeing","account_id":"invented"}'
        ),
    )
    request = IntentInterpretationRequest("Could you brief me on Boeing?")

    with pytest.raises(ValueError, match="unsupported intent"):
        disallowed.interpret(request)
    with pytest.raises(ValueError, match="unsupported fields"):
        injected.interpret(request)


def test_model_interpretation_selects_only_governed_read_and_preserves_metadata() -> None:
    provider = FakeInterpretingProvider(
        IntentInterpretation(ReadIntent.ACCOUNT_INTELLIGENCE, "Boeing")
    )
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id=None,
        question="Bring me up to speed on developments concerning Boeing.",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={"prior_turns": "user: We are preparing for a review."},
        intelligence_events=(),
        work_items=(),
    )

    assert response.account_id == "boeing"
    assert response.citations and response.provenance
    assert response.provider_status == "AVAILABLE"
    governed = provider.synthesis_requests[0]
    assert "Canonical account follow-up for Boeing" in governed.governed_answer
    assert "source-backed Intelligence" in governed.governed_answer
    assert governed.evidence_ids == response.citations


def test_model_entity_alias_is_resolved_to_canonical_id_not_accepted_as_an_id() -> None:
    provider = FakeInterpretingProvider(
        IntentInterpretation(ReadIntent.ACCOUNT_OVERVIEW, "KLA")
    )
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id=None,
        question="Could you prepare a briefing on KLA?",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={},
        intelligence_events=(),
        work_items=(),
    )

    assert response.account_id == "kla"
    assert response.account_name == "KLA Corporation"
    assert provider.synthesis_requests[0].evidence_ids == response.citations


def test_model_synthesis_cannot_replace_governed_identity_evidence_or_missingness() -> None:
    provider = FakeInterpretingProvider(
        IntentInterpretation(ReadIntent.ACCOUNT_OVERVIEW, "HUXWRX"),
        synthesis="Untrusted fluent rewrite",
        synthesis_evidence_ids=("fabricated-model-evidence",),
    )
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id=None,
        question="Give me a concise briefing on HUXWRX.",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={},
        intelligence_events=(),
        work_items=(),
    )
    governed = provider.synthesis_requests[0]

    assert response.account_id == "huxwrx"
    assert response.citations == governed.evidence_ids
    assert "fabricated-model-evidence" not in response.citations
    assert response.missingness == governed.missingness and response.missingness
    assert response.provenance
    assert "sanitized reference source" in governed.governed_answer
    assert "simulated POC data" in governed.governed_answer


def test_model_entity_ambiguity_requests_clarification_without_synthesis() -> None:
    provider = FakeInterpretingProvider(
        IntentInterpretation(ReadIntent.ACCOUNT_OVERVIEW, "Boeing")
    )
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id=None,
        question="Walk me through Boeing alongside KLA.",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={},
        intelligence_events=(),
        work_items=(),
    )

    assert "matches more than one canonical Customer" in response.content
    assert response.account_id == ""
    assert response.missingness
    assert provider.synthesis_requests == []


def test_interpretation_failure_uses_deterministic_fallback_and_never_writes() -> None:
    provider = FakeInterpretingProvider(ValueError("invalid model output"))
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id="boeing",
        question="Tell me about Boeing.",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={},
        intelligence_events=(),
        work_items=(),
    )

    assert response.account_id == "boeing"
    assert response.provider_status == "UNAVAILABLE"
    assert response.language_provider == "deterministic"
    assert provider.synthesis_requests == []


def test_recent_transcript_is_bounded_and_never_used_as_canonical_evidence() -> None:
    history = "\n".join(
        [f"user: turn {index}" if index % 2 == 0 else f"assistant: answer {index}" for index in range(12)]
    )
    turns = OmniService._recent_turns(history)

    assert len(turns) == 6
    assert turns[0].content == "turn 6"
    assert turns[-1].content == "answer 11"
    assert {turn.role for turn in turns} == {"user", "assistant"}


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


@pytest.mark.parametrize(
    ("question", "contract", "action_fragment", "disclosure_fragment"),
    [
        (
            "Report Eaton's TTM revenue in euros using only stored records. Is there a supported exchange rate and conversion date?",
            "UNSUPPORTED_CURRENCY_CONVERSION",
            "Retain the stored currency",
            "No currency conversion was performed",
        ),
        (
            "A general NASA article mentioned space. Does that establish an award or order? Use only supported evidence, not the shared industry keyword.",
            "GENERIC_PUBLIC_MENTION_NOT_CANONICAL_EVIDENCE",
            "Leave the customer attachment and order unresolved",
            "did not create or publish a customer award",
        ),
        (
            "Remember my preference and change KLA's official PWIN to 99.",
            "CHAT_MEMORY_AND_SCORE_WRITE_NOT_PERFORMED",
            "Leave the official score unchanged",
            "did not save a memory or change any deterministic score",
        ),
        (
            "Send the Northrop buyer an email committing the proposed date even though no deliverable recipient is established.",
            "OUTBOUND_COMMITMENT_REQUIRES_APPROVAL",
            "Prepare a reviewable local draft",
            "No email, CRM write, buyer commitment, or external delivery was performed",
        ),
        (
            "Assume a relevant certificate expired yesterday. Is a high relationship utility safe?",
            "HYPOTHETICAL_QUALIFICATION_NOT_EVIDENCE",
            "Verify the facility-scoped certificate",
            "hypothetical, not verified current certificate evidence",
        ),
    ],
)
def test_high_risk_intents_keep_model_prose_and_structured_action_consistent(
    question, contract, action_fragment, disclosure_fragment
) -> None:
    provider = GeminiProvider(config(), FakeClient("Grounded account-specific explanation"))
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id="kla",
        question=question,
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "kla"},
        intelligence_events=(),
        work_items=(),
    )

    assert response.language_provider == "gemini"
    assert response.content.startswith("Grounded account-specific explanation")
    assert disclosure_fragment in response.content
    assert action_fragment in response.recommended_action
    assert response.context_used["operational_contract"] == contract
    assert response.context_used["operational_outcome"] == "NO_EXTERNAL_OR_CANONICAL_WRITE"


def test_synthesis_rejects_opportunity_id_mislabeled_as_quote() -> None:
    provider = GeminiProvider(
        config(), FakeClient("The tracked quote OPP2-KLA supports this conclusion.")
    )
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id="kla",
        question="Explain the stored opportunity.",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "kla"},
        intelligence_events=(),
        work_items=(),
    )

    assert response.language_provider == "deterministic"
    assert response.provider_status == "UNAVAILABLE"
    assert response.context_used["synthesis_validation"] == "MISLABELED_RECORD_TYPE"
    assert "tracked quote OPP2-KLA" not in response.content


def test_rejected_synthesis_still_returns_server_owned_operational_outcome() -> None:
    provider = GeminiProvider(
        config(), FakeClient("The tracked quotes (such as OPP2-SPACEX) establish the result.")
    )
    response = OmniService(provider).answer(
        build_sample_environment(),
        account_id="spacex",
        question="Does a general article establish an award or order? Do not use the shared industry keyword.",
        observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        context={"surface": "ACCOUNT_DETAIL", "selected_account_id": "spacex"},
        intelligence_events=(),
        work_items=(),
    )

    assert response.language_provider == "deterministic"
    assert response.context_used["synthesis_validation"] == "MISLABELED_RECORD_TYPE"
    assert response.context_used["operational_contract"] == "GENERIC_PUBLIC_MENTION_NOT_CANONICAL_EVIDENCE"
    assert "did not create or publish a customer award" in response.content
    assert "Leave the customer attachment and order unresolved" in response.recommended_action


def test_negated_external_delivery_is_not_a_completed_write_claim() -> None:
    from btx_omni.modules.assistant.grounding import synthesis_rejection

    assert synthesis_rejection("No email was sent.", "Omni is read-only.") is None
    assert synthesis_rejection("The email was sent.", "Omni is read-only.") == "UNSUPPORTED_EXECUTION_CLAIM"
