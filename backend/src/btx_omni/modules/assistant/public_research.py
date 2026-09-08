"""Bounded public-web research helpers for Omni's read-only conversation path."""

from __future__ import annotations

import re

from btx_omni.ai.contracts import (
    PublicEvidenceRecord,
    PublicWebFinding,
    PublicWebResearchRequest,
)


def safe_public_research_request(question: str, canonical_public_name: str) -> PublicWebResearchRequest:
    """Only public identity and allow-listed topic labels enter search grounding.

    Never forward user text, internal transaction passages, memory or prior turns
    to a search-enabled provider. Gemini language synthesis has a separate contract.
    """
    topics = {"award": "public contract announcements", "contract": "public contract announcements",
              "supplier": "public supplier announcements", "contact": "published professional roles",
              "capacity": "public facility expansion announcements", "program": "public product and program announcements"}
    selected = sorted({topic for term, topic in topics.items() if term in question.casefold()})
    return PublicWebResearchRequest(
        query=f"{canonical_public_name}: " + "; ".join(selected[:3] or ["recent public manufacturing news"]),
        subject_display_name=canonical_public_name,
        governed_context=(),
    )


def should_research_public_web(question: str, *, has_selected_evidence: bool = False) -> bool:
    """Broad current/external research trigger; governed-only queries stay deterministic."""
    query = question.casefold()
    if any(term in query for term in ('using only the stored records', 'use only stored records', 'do not search', 'without web search')):
        return False
    explicit_research = bool(re.search(r'\b(search|research|look up|look for)\b', query))
    if not explicit_research and (re.search(r'\b(assume|hypothetical|hypothetically)\b', query)
                                  or 'shared industry keyword' in query):
        return False
    if has_selected_evidence and not any(term in query for term in ("search", "look up", "look for", "latest", "current", "recent", "today", "this week", "new sources", "more sources")):
        return False
    internal_only = (
        "score",
        "attractiveness",
        "open action",
        "my action",
        "relationship path",
        "approval",
    )
    if any(term in query for term in internal_only):
        return False
    research_terms = (
        "research",
        "current",
        "recent",
        "this week",
        "news",
        "happened",
        "changed",
        "public supplier",
        "supplier",
        "award",
        "contract",
        "program",
        "components",
        "system",
        "evidence",
        "web",
        "look for",
        "technical",
    )
    # 'A researched contact' describes an existing record, not a new research
    # instruction. Avoid substring triggers that leak irrelevant search into a
    # fully answerable internal-history question.
    return any(re.search(rf'\b{re.escape(term)}\b', query) for term in research_terms)


def public_findings_to_evidence(
    findings: tuple[PublicWebFinding, ...],
) -> tuple[PublicEvidenceRecord, ...]:
    """Make bounded cited public findings eligible input for Phase 24A/B decomposition.

    This is only a conversion to public evidence content. It does not create a
    canonical record, taxonomy entry, match, relationship, or any internal fact.
    """
    return tuple(
        PublicEvidenceRecord(
            evidence_id=item.evidence_id,
            title=item.title,
            extract=item.extract,
            source_url=item.url,
            provenance=f"PUBLIC_WEB:{item.publisher}:{item.retrieval_provenance}",
        )
        for item in findings[:6]
    )
