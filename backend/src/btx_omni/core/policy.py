"""Deterministic policy decisions for model context and human actions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from btx_omni.core.classification import Classification, SensitivityTag


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    HUMAN_CONFIRMATION_REQUIRED = "HUMAN_CONFIRMATION_REQUIRED"


@dataclass(frozen=True)
class ModelContextPolicy:
    decision: PolicyDecision
    reason: str


def model_context_policy(
    classification: Classification, sensitivity_tags: frozenset[SensitivityTag] = frozenset()
) -> ModelContextPolicy:
    if classification not in {Classification.PUBLIC, Classification.INTERNAL_COMMERCIAL}:
        return ModelContextPolicy(PolicyDecision.DENY, "classification is not eligible for model context")
    if sensitivity_tags:
        return ModelContextPolicy(PolicyDecision.DENY, "sensitivity tags require exclusion from model context")
    return ModelContextPolicy(PolicyDecision.ALLOW, "governed source context is eligible")
