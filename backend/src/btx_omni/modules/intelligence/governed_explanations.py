"""Worker-safe governed explanation service with deterministic fallback."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from btx_omni.ai.contracts import (
    GovernedExplanation,
    GovernedExplanationRequest,
    LanguageProvider,
    LanguageProviderError,
    ProviderStatus,
)


@dataclass(frozen=True)
class ExplanationRetryPolicy:
    auth_failed_seconds: int = 3600
    timeout_seconds: int = 300
    quota_seconds: int = 21600
    unavailable_seconds: int = 900
    def cooldown(self, status: ProviderStatus) -> timedelta | None:
        value = {ProviderStatus.AUTH_FAILED: self.auth_failed_seconds, ProviderStatus.TIMEOUT: self.timeout_seconds, ProviderStatus.QUOTA: self.quota_seconds, ProviderStatus.UNAVAILABLE: self.unavailable_seconds}.get(status)
        return timedelta(seconds=value) if value else None


@dataclass(frozen=True)
class ExplanationProjection:
    provider_status: ProviderStatus
    summary: str
    key_drivers: tuple[str, ...]
    limitations: tuple[str, ...]
    what_to_consider: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provider: str | None
    model: str | None
    assisted: bool
    disclosure: str = "Explanation assisted by Gemini; underlying result is deterministic."


def cache_key(request: GovernedExplanationRequest, *, model: str = "") -> str:
    content = (request.contract_version, request.prompt_version, request.explanation_type.value, request.subject_type, request.subject_display_name, request.deterministic_result, request.deterministic_status, request.numeric_value or "", request.score_unit or "", request.configuration_version or "", request.data_mode, request.hypothesis_or_calibration or "", request.style, model, *request.key_drivers, *request.limiting_factors, *request.deterministic_matches, *request.missingness, *request.evidence_ids)
    return hashlib.sha256("\x1f".join(content).encode()).hexdigest()


def _persisted_projection(record: dict) -> ExplanationProjection:
    payload = __import__("json").loads(record["projection"])
    return ExplanationProjection(
        ProviderStatus(payload["provider_status"]),
        payload["summary"],
        tuple(payload["key_drivers"]),
        tuple(payload["limitations"]),
        tuple(payload["what_to_consider"]),
        tuple(payload["evidence_ids"]),
        record.get("provider"),
        record.get("model"),
        bool(payload["assisted"]),
        payload["disclosure"],
    )


def deterministic_fallback(request: GovernedExplanationRequest, status: ProviderStatus) -> ExplanationProjection:
    drivers = request.key_drivers[:3]
    limits = (*request.limiting_factors[:3], *request.missingness[:3])
    summary = request.deterministic_result
    if limits:
        summary += " Available context is incomplete; review the listed limitations before drawing commercial conclusions."
    return ExplanationProjection(status, summary, drivers, limits, request.deterministic_matches[:3], request.evidence_ids, None, None, False)


def seller_projection(value: ExplanationProjection) -> dict:
    return {"provider_status": value.provider_status.value, "assisted": value.assisted, "summary": value.summary,
            "key_drivers": list(value.key_drivers), "limitations": list(value.limitations),
            "what_to_consider": list(value.what_to_consider), "evidence_ids": list(value.evidence_ids), "disclosure": value.disclosure}


class GovernedExplanationService:
    """Called by bounded processing only. It cannot replace deterministic inputs."""
    def process(self, request: GovernedExplanationRequest, provider: LanguageProvider, repository: object, *, subject_key: str, now: datetime | None = None, retry_policy: ExplanationRetryPolicy | None = None) -> ExplanationProjection:
        clock = now or datetime.now(UTC)
        model = str(getattr(getattr(provider, "config", None), "model", ""))
        key = cache_key(request, model=model)
        cached = repository.governed_explanation(subject_key, request.explanation_type.value, key)
        attempts = int(cached.get("attempt_count", 0)) if cached else 0
        if cached and cached.get("governed_content_hash") == key and cached.get("status") in (ProviderStatus.AVAILABLE.value, ProviderStatus.NOT_CONFIGURED.value):
            return _persisted_projection(cached)
        if cached and cached.get("governed_content_hash") == key and cached.get("next_retry_at") and cached["next_retry_at"] > clock:
            return _persisted_projection(cached)
        if not provider.configured:
            projection = deterministic_fallback(request, ProviderStatus.NOT_CONFIGURED)
        elif provider.configured:
          try:
            result: GovernedExplanation = provider.explain_governed_result(request)
            if (
                result.explanation_type is not request.explanation_type
                or result.contract_version != request.contract_version
            ):
                raise ValueError("Provider explanation contract does not match request.")
            if not set(result.evidence_ids).issubset(request.evidence_ids):
                raise ValueError("Provider explanation contains unsupported evidence.")
            projection = ExplanationProjection(ProviderStatus.AVAILABLE, result.summary, result.key_drivers, result.limitations, result.what_to_consider, result.evidence_ids, result.provider, result.model, True)
          except LanguageProviderError as error:
            projection = deterministic_fallback(request, error.status)
          except (RuntimeError, ValueError):
            projection = deterministic_fallback(request, ProviderStatus.UNAVAILABLE)
        delay = (retry_policy or ExplanationRetryPolicy()).cooldown(projection.provider_status)
        repository.save_governed_explanation(subject_key=subject_key, explanation_type=request.explanation_type.value, governed_content_hash=key, projection=seller_projection(projection), provider=projection.provider, model=projection.model, status=projection.provider_status.value, attempt_count=attempts + 1, next_retry_at=clock + delay if delay else None, processed_at=clock)
        return projection
