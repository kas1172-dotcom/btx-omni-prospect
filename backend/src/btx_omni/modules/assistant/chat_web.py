"""Search grounding with a closed public-field query builder, never raw questions."""
import re
from enum import StrEnum

from btx_omni.ai.contracts import PublicWebResearchRequest


class PublicTopic(StrEnum):
    NEWS = "latest company news"
    PRODUCTION = "aircraft production ramp"
    REGULATIONS = "latest regulations"
    MARKET = "market developments"
    AWARDS = "public contract awards"
    COMPANY = "public company overview"
    NAICS = "NAICS industry classification"
    SCIENCE = "science and technology news"
    ECONOMY = "economic developments"


def public_query(topic: PublicTopic, company: str | None) -> str:
    # Neither a free-form query nor internal program/contact fields are accepted.
    if company and (len(company) > 160 or re.search(r"[\r\n@<>]|https?://", company)):
        raise ValueError("No safe public company name is available.")
    return " ".join(part for part in (company, PublicTopic(topic).value) if part)


def search(provider, query, company, now):
    result = provider.research_public_web(PublicWebResearchRequest(
        query=query, subject_display_name=company, governed_context=(), max_findings=3))
    findings = []
    for item in result.findings:
        # Do not relay instruction-bearing extracts into the conversation model.
        extract = item.extract
        if re.search(r"ignore.{0,40}(rules|instructions)|reveal.{0,30}(prompt|secret)|system prompt", extract, re.IGNORECASE):
            extract = "Source text was withheld because it contained instructions rather than usable research."
        findings.append({"id": item.evidence_id, "title": item.title, "publisher": item.publisher,
                         "url": item.url, "publication_date": None, "retrieved_at": now.isoformat(),
                         "extract": extract[:1600]})
    return {"findings": findings, "limitations": [*result.limitations,
            "Publication dates were not supplied by search grounding. Public sources do not establish BTX orders, supply or introductions."],
            "canonical_evidence": False}
