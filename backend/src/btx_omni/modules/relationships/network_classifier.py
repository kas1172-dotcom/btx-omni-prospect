"""Deterministic imported-title classification; no model or fuzzy inference."""
from __future__ import annotations

import re
from dataclasses import dataclass

CLASSIFIER_VERSION = "NETWORK_TITLE_RULES_1"
ROLE_FAMILIES = (
    "procurement", "supply_chain", "supplier_management", "engineering",
    "manufacturing", "operations", "unclassified",
)
SENIORITY_TIERS = ("executive", "director", "manager", "individual", "unclassified")

_ROLE_RULES = (
    ("supplier_management", (r"supplier (?:quality|development|management|manager)", r"vendor management")),
    ("procurement", (r"procurement", r"purchas(?:ing|er)", r"strategic sourc", r"commodity manager", r"buyer")),
    ("supply_chain", (r"supply chain", r"logistics", r"materials? planning", r"inventory")),
    ("manufacturing", (r"manufactur", r"production", r"plant manager", r"factory")),
    ("engineering", (r"engineer", r"technical", r"r&d", r"research and development")),
    ("operations", (r"operations?", r"chief operating officer", r"\bcoo\b")),
)
_SENIORITY_RULES = (
    ("executive", (r"\bchief\b", r"\bceo\b", r"\bcoo\b", r"\bcfo\b", r"\bcto\b", r"\bcio\b", r"president", r"vice president", r"\bvp\b", r"executive")),
    ("director", (r"director", r"head of")),
    ("manager", (r"manager", r"supervisor", r"lead")),
    ("individual", (r"engineer", r"specialist", r"analyst", r"buyer", r"planner", r"coordinator", r"associate")),
)


@dataclass(frozen=True)
class TitleClassification:
    role_family: str
    seniority_tier: str
    classifier_version: str = CLASSIFIER_VERSION


def _first_match(value: str, rules: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    return next((label for label, patterns in rules if any(re.search(pattern, value) for pattern in patterns)), "unclassified")


def classify_title(title: str | None) -> TitleClassification:
    normalized = " ".join((title or "").casefold().split())
    if not normalized:
        return TitleClassification("unclassified", "unclassified")
    return TitleClassification(_first_match(normalized, _ROLE_RULES), _first_match(normalized, _SENIORITY_RULES))
