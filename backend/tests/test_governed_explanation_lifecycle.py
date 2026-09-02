from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine

from btx_omni.ai.contracts import (
    ExplanationType,
    GovernedExplanation,
    GovernedExplanationRequest,
    LanguageProviderError,
    ProviderStatus,
)
from btx_omni.modules.intelligence.governed_explanations import (
    GovernedExplanationService,
    cache_key,
)
from btx_omni.monitor.repository import MonitorRepository


class FakeProvider:
    configured = True
    name = "fake-gemini"
    config = type("Config", (), {"model": "fake-explanation-v1"})()
    calls = 0

    def explain_governed_result(self, request: GovernedExplanationRequest) -> GovernedExplanation:
        self.calls += 1
        return GovernedExplanation("Boeing is structurally attractive.", ("Program durability", "Manufacturing fit"), ("Commercial context incomplete",), ("Validate connected commercial evidence",), ("ev-1",), request.explanation_type, self.name, self.config.model, request.contract_version)


def test_available_projection_round_trips_through_postgresql(monkeypatch) -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    repository = MonitorRepository(create_engine(url))
    request = GovernedExplanationRequest(ExplanationType.CUSTOMER_ATTRACTIVENESS, "CUSTOMER", "Boeing", "78 structural index; 82% coverage.", "AVAILABLE", key_drivers=("Program durability", "Manufacturing fit"), limiting_factors=("Connected commercial context unavailable",), evidence_ids=("ev-1",), data_mode="SAMPLE", hypothesis_or_calibration="Simulated hypothesis")
    provider = FakeProvider()
    subject_key = f"account:boeing:{uuid4()}"
    first = GovernedExplanationService().process(request, provider, repository, subject_key=subject_key, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert provider.calls == 1
    assert first.assisted and first.provider_status.value == "AVAILABLE"
    row = repository.governed_explanation(subject_key, request.explanation_type.value, __import__("btx_omni.modules.intelligence.governed_explanations", fromlist=["cache_key"]).cache_key(request, model="fake-explanation-v1"))
    assert row and row["attempt_count"] == 1 and row["next_retry_at"] is None
    second = GovernedExplanationService().process(request, provider, MonitorRepository(create_engine(url)), subject_key=subject_key, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert provider.calls == 1
    assert second == first


def test_quota_cooldown_and_evidence_rejection_are_durable() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    request = GovernedExplanationRequest(ExplanationType.CUSTOMER_ATTRACTIVENESS, "CUSTOMER", "Boeing", "78 structural index.", "AVAILABLE", key_drivers=("Manufacturing fit",), limiting_factors=("Prism revenue unavailable", "HubSpot activity unavailable"), evidence_ids=("ev-1", "ev-2"), data_mode="SAMPLE")
    class Provider(FakeProvider):
        mode = "quota"
        def explain_governed_result(self, value):
            self.calls += 1
            if self.mode == "quota":
                raise LanguageProviderError(ProviderStatus.QUOTA)
            if self.mode == "bad":
                return GovernedExplanation("bad", (), (), (), ("fake-999",), value.explanation_type, self.name, self.config.model, value.contract_version)
            return GovernedExplanation("Boeing is structurally attractive.", ("Program durability",), ("Commercial context incomplete",), ("Validate connected commercial evidence",), ("ev-1",), value.explanation_type, self.name, self.config.model, value.contract_version)
    provider = Provider(); repository = MonitorRepository(create_engine(url)); clock = datetime(2026, 1, 1, tzinfo=UTC); subject_key = f"quota:{uuid4()}"
    first = GovernedExplanationService().process(request, provider, repository, subject_key=subject_key, now=clock)
    assert first.provider_status is ProviderStatus.QUOTA and not first.assisted and provider.calls == 1
    row = repository.governed_explanation(subject_key, request.explanation_type.value, cache_key(request, model="fake-explanation-v1")); assert row and row["attempt_count"] == 1 and row["next_retry_at"] > clock
    second = GovernedExplanationService().process(request, provider, MonitorRepository(create_engine(url)), subject_key=subject_key, now=clock + __import__("datetime").timedelta(seconds=1))
    assert second.provider_status is ProviderStatus.QUOTA and provider.calls == 1
    provider.mode = "ok"
    third = GovernedExplanationService().process(request, provider, repository, subject_key=subject_key, now=clock + __import__("datetime").timedelta(seconds=21601))
    assert third.provider_status is ProviderStatus.AVAILABLE and third.assisted and provider.calls == 2
    provider.mode = "bad"
    changed = GovernedExplanationRequest(ExplanationType.CUSTOMER_ATTRACTIVENESS, "CUSTOMER", "Boeing", "79 structural index.", "AVAILABLE", evidence_ids=("ev-1", "ev-2"), data_mode="SAMPLE")
    invalid = GovernedExplanationService().process(changed, provider, repository, subject_key=f"bad:{uuid4()}", now=clock)
    assert invalid.provider_status is ProviderStatus.UNAVAILABLE and "fake-999" not in invalid.evidence_ids


def test_unavailable_fallback_is_durably_reused_during_cooldown() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    request = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        limiting_factors=("Prism revenue unavailable",),
        missingness=("HubSpot activity unavailable", "Paperless quote history unavailable"),
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
    )

    class UnavailableProvider(FakeProvider):
        def explain_governed_result(self, value: GovernedExplanationRequest) -> GovernedExplanation:
            self.calls += 1
            raise LanguageProviderError(ProviderStatus.UNAVAILABLE)

    provider = UnavailableProvider()
    subject_key = f"unavailable:{uuid4()}"
    repository = MonitorRepository(create_engine(url))
    first = GovernedExplanationService().process(
        request, provider, repository, subject_key=subject_key, now=clock
    )
    assert provider.calls == 1
    assert first.provider_status is ProviderStatus.UNAVAILABLE
    assert not first.assisted and first.summary
    assert set(first.evidence_ids).issubset(request.evidence_ids)
    assert "Prism revenue unavailable" in first.limitations
    assert "HubSpot activity unavailable" in first.limitations
    assert "no relationship" not in first.summary.lower()
    assert "not a fit" not in first.summary.lower()

    key = cache_key(request, model="fake-explanation-v1")
    row = repository.governed_explanation(subject_key, request.explanation_type.value, key)
    assert row and row["attempt_count"] == 1
    assert row["next_retry_at"] and row["next_retry_at"] > clock
    persisted_retry_at = row["next_retry_at"]
    assert json.loads(row["projection"])["assisted"] is False

    second = GovernedExplanationService().process(
        request,
        provider,
        MonitorRepository(create_engine(url)),
        subject_key=subject_key,
        now=clock + timedelta(seconds=1),
    )
    row_after = repository.governed_explanation(subject_key, request.explanation_type.value, key)
    assert provider.calls == 1
    assert second.provider_status is ProviderStatus.UNAVAILABLE
    assert not second.assisted
    assert row_after and row_after["attempt_count"] == 1
    assert row_after["next_retry_at"] == persisted_retry_at


def test_not_configured_fallback_is_durably_reused_without_provider_calls() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    request = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
    )

    class NotConfiguredProvider(FakeProvider):
        configured = False

        def explain_governed_result(self, value: GovernedExplanationRequest) -> GovernedExplanation:
            self.calls += 1
            raise AssertionError("A not-configured provider must not be invoked")

    provider = NotConfiguredProvider()
    subject_key = f"not-configured:{uuid4()}"
    repository = MonitorRepository(create_engine(url))
    first = GovernedExplanationService().process(
        request, provider, repository, subject_key=subject_key, now=clock
    )
    assert provider.calls == 0
    assert first.provider_status is ProviderStatus.NOT_CONFIGURED
    assert not first.assisted

    key = cache_key(request, model="fake-explanation-v1")
    row = repository.governed_explanation(subject_key, request.explanation_type.value, key)
    assert row and row["attempt_count"] == 1
    assert json.loads(row["projection"])["provider_status"] == ProviderStatus.NOT_CONFIGURED.value

    second = GovernedExplanationService().process(
        request,
        provider,
        MonitorRepository(create_engine(url)),
        subject_key=subject_key,
        now=clock + timedelta(days=1),
    )
    row_after = repository.governed_explanation(subject_key, request.explanation_type.value, key)
    assert provider.calls == 0
    assert second == first
    assert row_after and row_after["attempt_count"] == 1


def test_malformed_provider_output_persists_safe_unavailable_fallback() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    request = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
    )

    class MalformedProvider(FakeProvider):
        def explain_governed_result(self, value: GovernedExplanationRequest) -> GovernedExplanation:
            self.calls += 1
            raise ValueError("Malformed structured Gemini response")

    provider = MalformedProvider()
    subject_key = f"malformed:{uuid4()}"
    repository = MonitorRepository(create_engine(url))
    result = GovernedExplanationService().process(
        request, provider, repository, subject_key=subject_key, now=clock
    )
    assert provider.calls == 1
    assert result.provider_status is ProviderStatus.UNAVAILABLE
    assert not result.assisted and result.summary
    assert set(result.evidence_ids).issubset(request.evidence_ids)

    row = repository.governed_explanation(
        subject_key,
        request.explanation_type.value,
        cache_key(request, model="fake-explanation-v1"),
    )
    assert row and row["status"] == ProviderStatus.UNAVAILABLE.value
    payload = json.loads(row["projection"])
    assert payload["assisted"] is False
    assert "Malformed structured Gemini response" not in row["projection"]


def test_governed_hash_invalidates_each_authoritative_input() -> None:
    request = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        key_drivers=("Program durability",),
        limiting_factors=("Commercial evidence incomplete",),
        missingness=("Prism revenue unavailable",),
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
        hypothesis_or_calibration="Hypothesis",
    )
    baseline = cache_key(request, model="fake-explanation-v1")
    variants = (
        replace(request, deterministic_result="79 structural index."),
        replace(request, deterministic_status="NEEDS_REVIEW"),
        replace(request, key_drivers=("Manufacturing fit",)),
        replace(request, limiting_factors=("Paperless quote history unavailable",)),
        replace(request, missingness=("HubSpot activity unavailable",)),
        replace(request, evidence_ids=("ev-2",)),
        replace(request, numeric_value="79"),
        replace(request, score_unit="STRUCTURAL_INDEX_0_TO_100"),
        replace(request, configuration_version="attractiveness-v2"),
        replace(request, style="SELLER_DETAILED"),
        replace(request, prompt_version="governed-explanation-v2"),
        replace(request, contract_version="governed-explanation-contract-v2"),
    )
    assert all(cache_key(variant, model="fake-explanation-v1") != baseline for variant in variants)
    assert cache_key(request, model="fake-explanation-v2") != baseline


def test_changed_governed_hash_starts_a_new_attempt_sequence() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    request_a = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
    )
    request_b = replace(request_a, deterministic_result="79 structural index.")
    provider = FakeProvider()
    repository = MonitorRepository(create_engine(url))
    subject_key = f"changed-hash:{uuid4()}"

    first = GovernedExplanationService().process(
        request_a, provider, repository, subject_key=subject_key, now=clock
    )
    reused = GovernedExplanationService().process(
        request_a,
        provider,
        MonitorRepository(create_engine(url)),
        subject_key=subject_key,
        now=clock,
    )
    assert first.assisted and reused.assisted and provider.calls == 1
    hash_a = cache_key(request_a, model="fake-explanation-v1")
    row_a = repository.governed_explanation(subject_key, request_a.explanation_type.value, hash_a)
    assert row_a and row_a["attempt_count"] == 1

    second = GovernedExplanationService().process(
        request_b, provider, repository, subject_key=subject_key, now=clock
    )
    hash_b = cache_key(request_b, model="fake-explanation-v1")
    row_b = repository.governed_explanation(subject_key, request_b.explanation_type.value, hash_b)
    assert hash_a != hash_b
    assert second.assisted and provider.calls == 2
    assert row_b and row_b["attempt_count"] == 1
    # The repository deliberately retains the current projection per subject/type.
    assert repository.governed_explanation(subject_key, request_a.explanation_type.value, hash_a) is None


def test_subject_and_explanation_type_records_are_isolated() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    provider = FakeProvider()
    repository = MonitorRepository(create_engine(url))
    subject = f"isolation:{uuid4()}"
    customer = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
    )
    federal = GovernedExplanationRequest(
        ExplanationType.FEDERAL_OPPORTUNITY_RELEVANCE,
        "FEDERAL_OPPORTUNITY",
        "Award 123",
        "Relevant based on verified NAICS fit.",
        "RELEVANT",
        evidence_ids=("ev-2",),
        data_mode="SAMPLE",
    )
    first_subject = f"subject-a:{uuid4()}"
    second_subject = f"subject-b:{uuid4()}"

    GovernedExplanationService().process(customer, provider, repository, subject_key=subject, now=clock)
    GovernedExplanationService().process(federal, provider, repository, subject_key=subject, now=clock)
    GovernedExplanationService().process(customer, provider, repository, subject_key=first_subject, now=clock)
    GovernedExplanationService().process(customer, provider, repository, subject_key=second_subject, now=clock)
    assert provider.calls == 4

    customer_hash = cache_key(customer, model="fake-explanation-v1")
    federal_hash = cache_key(federal, model="fake-explanation-v1")
    assert repository.governed_explanation(subject, customer.explanation_type.value, customer_hash)
    assert repository.governed_explanation(subject, federal.explanation_type.value, federal_hash)
    assert repository.governed_explanation(first_subject, customer.explanation_type.value, customer_hash)
    assert repository.governed_explanation(second_subject, customer.explanation_type.value, customer_hash)

    GovernedExplanationService().process(customer, provider, repository, subject_key=subject, now=clock)
    GovernedExplanationService().process(federal, provider, repository, subject_key=subject, now=clock)
    GovernedExplanationService().process(customer, provider, repository, subject_key=first_subject, now=clock)
    GovernedExplanationService().process(customer, provider, repository, subject_key=second_subject, now=clock)
    assert provider.calls == 4


def test_provider_cannot_cross_explanation_contract_boundary() -> None:
    url = __import__("os").environ["BTX_DATABASE_URL"]
    request = GovernedExplanationRequest(
        ExplanationType.CUSTOMER_ATTRACTIVENESS,
        "CUSTOMER",
        "Boeing",
        "78 structural index.",
        "AVAILABLE",
        evidence_ids=("ev-1",),
        data_mode="SAMPLE",
    )

    class WrongContractProvider(FakeProvider):
        def explain_governed_result(self, value: GovernedExplanationRequest) -> GovernedExplanation:
            self.calls += 1
            return GovernedExplanation(
                "Wrong contract.",
                (),
                (),
                (),
                ("ev-1",),
                ExplanationType.FEDERAL_OPPORTUNITY_RELEVANCE,
                self.name,
                self.config.model,
                value.contract_version,
            )

    outcome = GovernedExplanationService().process(
        request,
        WrongContractProvider(),
        MonitorRepository(create_engine(url)),
        subject_key=f"wrong-contract:{uuid4()}",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert outcome.provider_status is ProviderStatus.UNAVAILABLE
    assert not outcome.assisted
