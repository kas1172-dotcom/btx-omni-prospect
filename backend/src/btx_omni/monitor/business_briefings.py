"""Account-specific business briefings over the existing canonical Monitor graph."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.monitor.briefs import SignalBrief
from btx_omni.monitor.documents import document_evidence
from btx_omni.monitor.policy import analysis_eligibility

RISK_TYPES = frozenset(
    {
        "CONTRACT_REDUCTION",
        "PROGRAM_CANCELLATION",
        "FACILITY_CLOSURE",
        "WORKFORCE_REDUCTION",
        "FINANCIAL_DISTRESS",
        "EXPORT_RESTRICTION",
        "PRODUCTION_DELAY",
        "REGULATORY_CHANGE",
        "SUPPLY_CHAIN_CHANGE",
    }
)
TECHNICAL_TYPES = frozenset(
    {
        "CONTRACT_AWARD",
        "CONTRACT_MODIFICATION",
        "SOLICITATION",
        "FACILITY_EXPANSION",
        "CAPACITY_EXPANSION",
        "NEW_FACILITY",
        "PROGRAM_LAUNCH",
        "PRODUCTION_RAMP",
        "PRODUCT_LAUNCH",
        "SUPPLIER_AWARD",
        "GOVERNMENT_FUNDING",
        "GRANT_AWARD",
    }
)
EXPANSION_TYPES = TECHNICAL_TYPES | {"CAPITAL_INVESTMENT", "PARTNERSHIP", "M_AND_A"}
RECORD_COLLECTIONS = (
    "rfqs",
    "quotes",
    "orders",
    "order_lines",
    "shipments",
    "service_issues",
    "service_events",
    "opportunities",
    "actions",
)


def requires_technical_investigation(event_type: str | None) -> bool:
    return bool(event_type in TECHNICAL_TYPES)


def _business_text(value: str | None) -> str:
    # Some authoritative legacy feeds expose the Windows-1252 trademark byte
    # as the Unicode C1 control U+0099. Normalize that display artifact while
    # retaining the original source record and revision for audit.
    return " ".join((value or "").replace("\x99", "™").split())


def _specific_headline(brief: SignalBrief) -> str:
    """Keep the recorded development visible without turning long source rows into UI copy."""
    changed = _business_text(brief.what_happened)
    if not changed:
        return brief.headline
    first, separator, remainder = changed.partition(";")
    if separator and first:
        suffix = " and related records" if remainder.strip() else ""
        candidate = f"{brief.headline}: {first.strip()}{suffix}"
    else:
        candidate = changed
    return candidate if len(candidate) <= 180 else candidate[:177].rstrip() + "…"


def _record_id(record: dict) -> str:
    return str(
        next(
            (value for key, value in record.items() if key.endswith("_id") and value),
            "record",
        )
    )


def _record_date(record: dict) -> str:
    values = [
        str(value)
        for key, value in record.items()
        if (key.endswith("_date") or key in {"date", "period"}) and value
    ]
    return max(values, default="")


def _selected_records(
    ledger: dict, program_id: str | None, component_ids: set[str]
) -> tuple[list[dict], str]:
    exact: list[dict] = []
    contextual: list[dict] = []
    scoped_line_ids = {
        row.get("order_line_id")
        for row in ledger.get("order_lines", ())
        if program_id and row.get("program_id") == program_id
    }
    scoped_order_ids = {
        row.get("order_id")
        for row in ledger.get("order_lines", ())
        if row.get("order_line_id") in scoped_line_ids
    }
    scoped_quote_ids = {
        row.get("quote_id")
        for row in ledger.get("orders", ())
        if row.get("order_id") in scoped_order_ids
    }
    scoped_rfq_ids = {
        row.get("rfq_id")
        for row in ledger.get("quotes", ())
        if row.get("quote_id") in scoped_quote_ids
    }
    for collection in RECORD_COLLECTIONS:
        for record in ledger.get(collection, ()):
            item = {
                "collection": collection,
                "record_id": _record_id(record),
                "date": _record_date(record),
            }
            for key in (
                "program_id",
                "component_id",
                "business_unit_id",
                "status",
                "stage",
                "title",
                "total_minor",
                "line_total_minor",
                "value_minor",
                "amount_minor",
                "quantity",
                "currency",
            ):
                if record.get(key) is not None:
                    item[key] = record[key]
            contextual.append(item)
            if (
                program_id
                and (
                    record.get("program_id") == program_id
                    or record.get("order_line_id") in scoped_line_ids
                    or record.get("order_id") in scoped_order_ids
                    or record.get("quote_id") in scoped_quote_ids
                    or record.get("rfq_id") in scoped_rfq_ids
                )
            ) or (component_ids and record.get("component_id") in component_ids):
                exact.append(item)
    selected = exact if exact else contextual
    selected.sort(
        key=lambda item: (item.get("date", ""), item["collection"], item["record_id"]),
        reverse=True,
    )
    return selected[:12], (
        "EXACT_PROGRAM"
        if exact and program_id
        else "EXACT_COMPONENT_INFERRED"
        if exact
        else "ACCOUNT_CONTEXT_ONLY"
    )


def _decision_projection(ledger: dict, *, account, revision: str | None) -> dict:
    decisions = customer_decisions(
        ledger,
        account_id=account.id,
        revision=revision or "unversioned",
        current_customer=account.relationship.value
        in {"CURRENT_CUSTOMER", "FORMER_CUSTOMER"},
    )
    return {
        key: {
            "score": value.get("score"),
            "status": value.get("status"),
            "coverage": value.get("coverage"),
            "factors": value.get("factors", ()),
            "missing_fields": value.get("missing_fields", ()),
        }
        for key, value in decisions.items()
        if isinstance(value, dict)
        and key in {"customer_health", "internal_commercial_risk"}
    }


def assemble_evidence_package(
    brief: SignalBrief, *, environment, repository, now: datetime | None = None
) -> dict:
    clock = now or datetime.now(UTC)
    accounts = {item.id: item for item in environment.accounts}
    account = (
        accounts.get(brief.canonical_account_ids[0])
        if len(brief.canonical_account_ids) == 1
        else None
    )
    source = (
        repository.event_document(brief.id, include_research=True)
        if repository
        else None
    )
    passages = document_evidence(source, max_passages=8)
    public = []
    for item in passages:
        try:
            metadata = json.loads(item.provenance or "{}")
        except json.JSONDecodeError:
            metadata = {}
        public.append(
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "source_url": item.source_url,
                "publication_date": metadata.get("publication_date"),
                "retrieved_at": metadata.get("retrieved_at"),
                "extraction_complete": metadata.get("extraction_complete"),
                "extract": item.extract,
                "truth_class": "PUBLIC_SOURCE",
            }
        )
    # Authoritative structured feeds (for example FDA and SAM) can be the
    # primary source record without an article/full-text document. Preserve
    # that distinction, citation, and extraction limitation instead of
    # incorrectly treating the event as having no public evidence.
    if not public and source and source.get("source_url") and source.get("title"):
        public.append(
            {
                "evidence_id": (
                    brief.evidence_ids[0]
                    if brief.evidence_ids
                    else source.get("observation_id")
                ),
                "title": _business_text(source["title"]),
                "source_url": source["source_url"],
                "publication_date": source.get("published_at"),
                "retrieved_at": source.get("retrieved_at"),
                "extraction_complete": False,
                "extract": source["title"],
                "record_kind": "STRUCTURED_SOURCE_RECORD",
                "truth_class": "PUBLIC_SOURCE",
            }
        )
    program = next(
        (
            item
            for item in environment.programs
            if item.id == brief.canonical_program_id
        ),
        None,
    )
    facility = next(
        (
            item
            for item in environment.facilities
            if item.id == brief.canonical_facility_id
        ),
        None,
    )
    technical = brief.technical_opportunity or {}
    fits = []
    for item in technical.get("matches", ())[:8]:
        units = item.get("business_units", ()) or (
            {
                "id": item.get("business_unit_id"),
                "name": item.get("business_unit_name"),
            },
        )
        for unit in units or ({},):
            fits.append(
                {
                    "candidate": item.get("candidate_name"),
                    "component": item.get("component_name"),
                    "component_id": item.get("component_id"),
                    "business_unit_id": unit.get("id"),
                    "business_unit": unit.get("name") or unit.get("id"),
                    "status": item.get("status"),
                    "evidence_ids": item.get("evidence_ids", ()),
                    "truth_class": "INFERRED_FIT",
                }
            )
    ledger = environment.commercial_ledgers.get(account.id) if account else None
    matched_component_ids = {
        str(item["component_id"])
        for item in fits
        if item.get("status") == "MATCHED" and item.get("component_id")
    }
    records, record_scope = (
        _selected_records(ledger, brief.canonical_program_id, matched_component_ids)
        if ledger
        else ([], "NO_INTERNAL_HISTORY")
    )
    for item in records:
        item["truth_class"] = "SIMULATED_INTERNAL_HISTORY"
        item["scope_basis"] = record_scope
    decisions = (
        _decision_projection(
            ledger, account=account, revision=environment.commercial_revision
        )
        if ledger and account
        else {}
    )
    has_exact_context = record_scope == "EXACT_PROGRAM"
    has_fit = any(
        item.get("status") in {"MATCHED", "POSSIBLE_MATCH_REVIEW_REQUIRED"}
        for item in fits
    )
    has_account_context = bool(records)
    analysis_state = analysis_eligibility(
        brief.publication_timestamp,
        collected_at=brief.collection_timestamp,
        now=clock,
    )
    if not account or not public or analysis_state != "ELIGIBLE":
        relevance = "INCOMPLETE" if account else "INFORMATIONAL"
    elif brief.event_type in RISK_TYPES and has_account_context:
        relevance = "ESTABLISHED_ACCOUNT_REVIEW"
    elif brief.event_type in EXPANSION_TYPES and has_exact_context:
        relevance = "ESTABLISHED_COMMERCIAL_RELEVANCE"
    elif brief.event_type in EXPANSION_TYPES and has_fit and has_account_context:
        relevance = "REVIEW_REQUIRED"
    else:
        relevance = "INFORMATIONAL"
    account_name = account.legal_name if account else "the unresolved organization"
    commercial_anchor = None
    for record in records:
        value = next(
            (
                record.get(key)
                for key in (
                    "total_minor",
                    "line_total_minor",
                    "amount_minor",
                    "value_minor",
                )
                if record.get(key) is not None
            ),
            None,
        )
        if value is not None:
            currency = record.get("currency") or (ledger or {}).get("currency") or "USD"
            amount = (
                f"{currency} {Decimal(value) / 100:,.2f}"
                if currency == "USD"
                else f"{value} {currency} minor units"
            )
            commercial_anchor = f"{amount} in the referenced {record['collection'].replace('_', ' ')} record"
            break
    if relevance == "ESTABLISHED_ACCOUNT_REVIEW":
        why = f"The development concerns {account_name}; BTX has account-scoped commercial history that warrants an exposure review. It does not by itself prove that a specific BTX program is affected."
        action = "Review the cited notice against open orders, shipments and issues before changing any customer commitment."
        rationale = (
            "Public risk and internal execution evidence must be reconciled before action."
            + (
                f" The package includes {commercial_anchor}."
                if commercial_anchor
                else ""
            )
        )
    elif relevance == "ESTABLISHED_COMMERCIAL_RELEVANCE":
        why = f"The development is linked to {account_name} and has scoped program or capability context alongside existing BTX commercial records."
        action = "Validate the technical fit and account scope, then prepare a governed customer follow-up."
        rationale = (
            "The evidence supports investigation, while qualification and customer need remain separate gates."
            + (
                f" The package includes {commercial_anchor}."
                if commercial_anchor
                else ""
            )
        )
    elif relevance == "REVIEW_REQUIRED":
        why = f"The development concerns {account_name} and suggests a possible capability fit, but the fit is not joined to a canonical program-specific BTX record."
        action = "Review program and component scope before deciding whether customer follow-up is warranted."
        rationale = "A broad capability and account history are insufficient to establish participation in this development."
    elif relevance == "INFORMATIONAL":
        why = f"The development is associated with {account_name}, but the current evidence does not establish a program-specific BTX commercial implication."
        action = None
        rationale = "Keep the item available for awareness; do not promote it as a seller priority without stronger scoped evidence."
    else:
        why = "The public record is retained, but identity, attributable passages, or analysis timing is incomplete."
        action = None
        rationale = "Complete the missing evidence before commercial use."
    uncertainties = []
    if record_scope == "ACCOUNT_CONTEXT_ONLY" and records:
        uncertainties.append(
            "Internal records are account context only; they are not evidence of participation in the public event."
        )
    if record_scope == "EXACT_COMPONENT_INFERRED":
        uncertainties.append(
            "The component join uses a reviewed technical fit; it does not prove BTX participation in the public event."
        )
    if not program:
        uncertainties.append("No canonical program is resolved for this event.")
    if requires_technical_investigation(brief.event_type) and not fits:
        uncertainties.append("No reviewed component or capability fit is available.")
    if not passages and public and requires_technical_investigation(brief.event_type):
        uncertainties.append(
            "The cited structured source record has no retained full-text passage; technical conclusions require further evidence."
        )
    elif not public:
        uncertainties.append("No attributable public source record is available.")
    headline = _specific_headline(brief)
    package = {
        "contract_version": "BTX_MONITOR_BUSINESS_BRIEF_1",
        "event_id": brief.id,
        "event_type": brief.event_type,
        "headline": headline,
        "what_changed": _business_text(brief.what_happened),
        "account": {
            "id": account.id,
            "name": account_name,
            "relationship": account.relationship.value,
        }
        if account
        else None,
        "facility": {"id": facility.id, "name": facility.name} if facility else None,
        "program": {"id": program.id, "name": program.name} if program else None,
        "markets": brief.markets,
        "public_evidence": public,
        "capability_fit": fits,
        "commercial_records": records,
        "commercial_record_scope": record_scope,
        "deterministic_scores": {
            "signal_confidence": brief.signal_confidence,
            "public_risk_severity": brief.risk_severity,
            **decisions,
        },
        "analysis_eligibility": analysis_state,
        "commercial_relevance_state": relevance,
        "priority_eligible": relevance
        in {"ESTABLISHED_ACCOUNT_REVIEW", "ESTABLISHED_COMMERCIAL_RELEVANCE"},
        "why_it_matters": why,
        "recommended_action": action,
        "action_rationale": rationale,
        "material_uncertainties": uncertainties,
        "provenance_boundaries": {
            "public": "PUBLIC_SOURCE",
            "internal": "SIMULATED_INTERNAL_HISTORY",
            "fit": "INFERRED_FIT",
        },
    }
    revision_payload = {
        key: package[key] for key in package if key not in {"analysis_eligibility"}
    }
    package["input_revision"] = hashlib.sha256(
        json.dumps(
            revision_payload, sort_keys=True, default=str, separators=(",", ":")
        ).encode()
    ).hexdigest()
    package["source_revision"] = source.get("content_hash") if source else None
    return package


def apply_evidence_package(brief: SignalBrief, package: dict) -> SignalBrief:
    account_id = (
        brief.canonical_account_ids[0]
        if len(brief.canonical_account_ids) == 1
        else None
    )
    next_step = package.get("recommended_action")
    seller_summary = str(package["why_it_matters"])
    if next_step:
        seller_summary = f"{seller_summary} Next: {next_step}"
    elif package.get("commercial_relevance_state") == "INFORMATIONAL":
        seller_summary = f"{seller_summary} No seller action is established from the current evidence."
    else:
        seller_summary = (
            f"{seller_summary} Complete the missing evidence before commercial use."
        )
    return replace(
        brief,
        context_id=f"{brief.id}:{account_id}" if account_id else brief.id,
        headline=str(package["headline"]),
        what_happened=str(package["what_changed"]),
        why_it_may_matter=str(package["why_it_matters"]),
        recommended_action=next_step,
        what_to_watch=str(package.get("action_rationale") or brief.what_to_watch),
        analysis_status="READY" if package.get("public_evidence") else "INCOMPLETE",
        commercial_relevance_state=str(package["commercial_relevance_state"]),
        priority_eligible=bool(package["priority_eligible"]),
        action_rationale=str(package["action_rationale"]),
        material_uncertainties=tuple(package.get("material_uncertainties", ())),
        references=tuple(
            {
                "evidence_id": row["evidence_id"],
                "title": row["title"],
                "url": row["source_url"],
                "publication_date": row.get("publication_date"),
            }
            for row in package.get("public_evidence", ())
        ),
        evidence_package=package,
        input_revision=package.get("input_revision"),
        generation_status="DETERMINISTIC_READY",
        seller_summary=seller_summary,
    )


def assessment_projection(brief: SignalBrief) -> dict:
    return {
        "headline": brief.headline,
        "what_happened": brief.what_happened,
        "why_it_may_matter": brief.why_it_may_matter,
        "recommended_action": brief.recommended_action,
        "action_rationale": brief.action_rationale,
        "material_uncertainties": brief.material_uncertainties,
        "references": brief.references,
        "evidence_ids": brief.evidence_ids,
        "analysis_status": brief.analysis_status,
        "commercial_relevance_state": brief.commercial_relevance_state,
        "priority_eligible": brief.priority_eligible,
        "evidence_package": brief.evidence_package,
        "generation_status": brief.generation_status,
        "seller_summary": brief.seller_summary,
        "summary_mode": brief.summary_mode,
    }


def persist_assessment(
    brief: SignalBrief,
    *,
    repository,
    now: datetime,
    provider: str | None = None,
    model: str | None = None,
) -> dict | None:
    if not brief.input_revision:
        return None
    account_id = (
        brief.canonical_account_ids[0]
        if len(brief.canonical_account_ids) == 1
        else None
    )
    business_units = sorted(
        {
            str(item.get("business_unit_id"))
            for item in (brief.evidence_package or {}).get("capability_fit", ())
            if item.get("business_unit_id")
        }
    )
    # The account-wide assessment remains canonical. BU-specific contexts can be
    # added without changing or misattributing the event's account/site scope.
    result = repository.save_intelligence_assessment(
        event_id=brief.id,
        account_id=account_id,
        business_unit_id=None,
        input_revision=brief.input_revision,
        source_revision=(brief.evidence_package or {}).get("source_revision"),
        projection={
            **assessment_projection(brief),
            "related_business_units": business_units,
        },
        generation_status=brief.generation_status,
        provider=provider,
        model=model,
        created_at=now,
    )
    for business_unit_id in business_units:
        package = brief.evidence_package or {}
        unit_package = {
            **package,
            "context_business_unit_id": business_unit_id,
            "capability_fit": [
                item
                for item in package.get("capability_fit", ())
                if item.get("business_unit_id") == business_unit_id
            ],
            "commercial_records": [
                item
                for item in package.get("commercial_records", ())
                if item.get("business_unit_id") == business_unit_id
            ],
        }
        unit_revision = hashlib.sha256(
            json.dumps(
                unit_package, sort_keys=True, default=str, separators=(",", ":")
            ).encode()
        ).hexdigest()
        repository.save_intelligence_assessment(
            event_id=brief.id,
            account_id=account_id,
            business_unit_id=business_unit_id,
            input_revision=unit_revision,
            source_revision=package.get("source_revision"),
            projection={
                **assessment_projection(brief),
                "evidence_package": unit_package,
                "related_business_units": [business_unit_id],
            },
            generation_status=brief.generation_status,
            provider=provider,
            model=model,
            created_at=now,
        )
    return result


def apply_persisted_assessment(
    brief: SignalBrief, persisted: dict | None
) -> SignalBrief:
    if not persisted or persisted.get("input_revision") != brief.input_revision:
        return brief
    projection = persisted.get("projection") or {}
    return replace(
        brief,
        headline=str(projection.get("headline") or brief.headline),
        what_happened=str(projection.get("what_happened") or brief.what_happened),
        why_it_may_matter=str(
            projection.get("why_it_may_matter") or brief.why_it_may_matter
        ),
        recommended_action=projection.get("recommended_action"),
        action_rationale=projection.get("action_rationale"),
        material_uncertainties=tuple(
            projection.get("material_uncertainties", brief.material_uncertainties)
        ),
        seller_summary=str(projection.get("seller_summary") or brief.seller_summary),
        summary_mode=str(projection.get("summary_mode") or brief.summary_mode),
        generation_status=str(
            projection.get("generation_status") or brief.generation_status
        ),
        assessment_id=str(persisted["id"]),
        assessment_version=int(persisted["version"]),
    )
