"""Bounded public-web research helpers for Omni's read-only conversation path."""

from __future__ import annotations

from btx_omni.ai.contracts import PublicEvidenceRecord, PublicWebFinding


def should_research_public_web(question: str) -> bool:
    """Broad current/external research trigger; governed-only queries stay deterministic."""
    query = question.casefold()
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
    return any(term in query for term in research_terms)


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
