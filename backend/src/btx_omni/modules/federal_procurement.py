"""Typed federal procurement projections; source facts never come from UI parsing."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from btx_omni.ai.contracts import ExplanationType
from btx_omni.modules.federal_opportunity_routing import (
    build_assessment,
    procurement_stage,
)
from btx_omni.modules.intelligence.governed_explanation_adapters import (
    federal_opportunity_subject_key,
    persisted_seller_explanation,
)

MARKETS = (
    "Commercial Aerospace",
    "Defense",
    "Space",
    "Semiconductor",
    "Medical",
    "Robotics",
    "Energy",
)
NOTICE = {
    "SOLICITATION": "Solicitation",
    "PRESOLICITATION": "Pre-Solicitation",
    "SOURCES_SOUGHT": "Sources Sought",
    "SPECIAL_NOTICE": "Special Notice",
    "AWARD_NOTICE": "Award Notice",
}


def v(p: dict[str, Any], *keys: str):
    return next((p[k] for k in keys if p.get(k) not in (None, "")), None)


def date(x: Any):
    try:
        d = datetime.fromisoformat(str(x)) if x else None
        return d if d and d.tzinfo else d.replace(tzinfo=UTC) if d else None
    except ValueError:
        return None


def amount(x: Any):
    try:
        return Decimal(str(x)) if x not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def normalize_notice_type(x: Any) -> tuple[str | None, bool]:
    if not x:
        return None, False
    key = str(x).upper().replace("-", "_").replace(" ", "_")
    key = {
        "PRE_SOLICITATION": "PRESOLICITATION",
        "SOURCES_SOUGHT_NOTICE": "SOURCES_SOUGHT",
    }.get(key, key)
    return NOTICE.get(key, str(x)), key == "SOURCES_SOUGHT"


def market_for(naics: str | None, agency: str | None = None) -> str:
    n = naics or ""
    a = (agency or "").lower()
    if n.startswith(("3364", "3365")):
        return "Commercial Aerospace"
    if n.startswith("3344"):
        return "Semiconductor"
    if n.startswith("3391"):
        return "Medical"
    if n.startswith("335"):
        return "Energy"
    if "nasa" in a or "space" in a:
        return "Space"
    if any(x in a for x in ("defense", "army", "navy", "air force")):
        return "Defense"
    return "UNRESOLVED"


def fiscal(d: datetime | None):
    return (
        d.year + 1 if d and d.month >= 10 else d.year if d else None,
        ((d.month - 10) % 12) // 3 + 1 if d else None,
    )


def opportunity(
    p: dict[str, Any],
    obs: Any,
    *,
    verified: bool,
    context: dict[str, Any] | None = None,
) -> dict:
    raw = v(p, "type", "noticeType", "notice_type")
    cat, sought = normalize_notice_type(raw)
    deadline = date(v(p, "responseDeadLine", "responseDeadline", "response_date"))
    n = v(p, "naicsCode", "naics", "naics_code")
    agency = v(p, "department", "fullParentPathName", "organizationName", "agency")
    stage = procurement_stage(raw, active=v(p, "active", "status"))
    return {
        "canonical_source_id": obs.id,
        "source": "SAM",
        "opportunity_id": obs.source_identity.source_record_id,
        "title": obs.title,
        "agency": agency,
        "office": v(p, "office", "subTier", "subAgency"),
        "posted_date": obs.source_published_at.isoformat()
        if obs.source_published_at
        else None,
        "response_deadline": deadline.isoformat() if deadline else None,
        "notice_type": raw,
        "notice_category": cat,
        "stage": stage,
        "sources_sought": sought,
        "set_aside": v(p, "typeOfSetAside", "setAside", "set_aside"),
        "naics": str(n) if n else None,
        "psc": v(p, "classificationCode", "psc"),
        "solicitation_number": v(p, "solicitationNumber", "solicitation_number"),
        "place_of_performance": v(p, "placeOfPerformance", "place_of_performance"),
        "description": v(p, "description", "descriptionText", "synopsis"),
        "official_source_url": obs.raw_evidence.locator,
        "evidence": {
            "id": obs.raw_evidence.id,
            "collected_at": obs.observed_at.isoformat(),
        },
        "freshness": {"collected_at": obs.observed_at.isoformat()},
        "history": {
            "first_seen_at": obs.source_version.first_seen_at.isoformat(),
            "last_seen_at": obs.source_version.last_seen_at.isoformat(),
        },
        "source_revision": obs.source_version.content_hash,
        "source_payload": p,
        "data_mode": "CONNECTED",
        "naics_targeting": "VERIFIED" if verified else "PENDING_CONFIRMATION",
        "market": market_for(str(n) if n else None, str(agency) if agency else None),
        "btx_context": context or {"state": "UNAVAILABLE", "data_mode": "UNAVAILABLE"},
        "missingness": [
            k
            for k, x in (
                ("response deadline", deadline),
                ("set-aside", v(p, "typeOfSetAside", "setAside", "set_aside")),
                ("NAICS", n),
                ("agency", agency),
            )
            if not x
        ],
    }


def award(p: dict[str, Any], obs: Any) -> dict:
    d = date(v(p, "Action Date", "action_date", "actionDate"))
    fy, fq = fiscal(d)
    x = amount(
        v(
            p,
            "Transaction Amount",
            "Award Amount",
            "federal_action_obligation",
            "award_amount",
        )
    )
    n = v(p, "NAICS", "naics_code", "naics")
    agency = v(p, "Awarding Agency", "awarding_agency_name")
    return {
        "canonical_source_id": obs.id,
        "source": "USASPENDING",
        "award_id": obs.source_identity.source_record_id,
        "recipient": v(p, "Recipient Name", "recipient_name"),
        "award_amount": str(x) if x is not None else None,
        "award_date": d.isoformat() if d else None,
        "fiscal_year": fy,
        "fiscal_quarter": fq,
        "naics": str(n) if n else None,
        "awarding_agency": agency,
        "description": v(p, "Description", "description"),
        "official_source_url": obs.raw_evidence.locator,
        "evidence": {
            "id": obs.raw_evidence.id,
            "collected_at": obs.observed_at.isoformat(),
        },
        "freshness": {"collected_at": obs.observed_at.isoformat()},
        "data_mode": "CONNECTED",
        "market": market_for(str(n) if n else None, str(agency) if agency else None),
        "canonical_customer": None,
        "missingness": [
            k
            for k, x in (("award amount", x), ("action date", d), ("NAICS", n))
            if x is None
        ],
    }


def relevance(x: dict[str, Any], *, now: datetime) -> dict:
    n = 40 if x.get("naics") and x.get("naics_targeting") == "VERIFIED" else 0
    b = 35 if x.get("btx_context", {}).get("aligned") else 0
    s = (
        15
        if x.get("sources_sought")
        else 10
        if x.get("notice_category") in {"Solicitation", "Pre-Solicitation"}
        else 0
    )
    d = date(x.get("response_deadline"))
    u = 10 if d and 0 <= (d - now).days <= 14 else 5 if d else 0
    fs = (
        (
            "Verified NAICS/capability alignment",
            40,
            n,
            "present" if n else "unavailable",
        ),
        (
            "Relevant BTX commercial context",
            35,
            b,
            x.get("btx_context", {}).get("state", "unavailable"),
        ),
        ("Official notice stage", 15, s, x.get("notice_category") or "unavailable"),
        (
            "Deadline actionability",
            10,
            u,
            f"{(d - now).days} days" if d else "unavailable",
        ),
    )
    score = sum(f[2] for f in fs)
    return {
        "score": score,
        "score_range": "0-100",
        "tier": "HIGH" if score >= 65 else "MEDIUM" if score >= 35 else "LOW",
        "configuration_version": "federal-opportunity-relevance-draft-v1",
        "calibration_label": "Draft relevance model — pending BTX calibration",
        "factors": [
            {"name": a, "weight": w, "points": p, "state": q, "available": bool(p)}
            for a, w, p, q in fs
        ],
        "missingness": [a for a, w, p, q in fs if not p],
    }


def period_comparison(
    current: list[dict[str, Any]], *, now: datetime, prior_count: int | None = None
) -> dict[str, Any]:
    """Fixed rolling seven-day contract; never turns missing history into zero."""
    start = now - timedelta(days=7)
    newly = sum(
        bool(
            x.get("history", {}).get("first_seen_at")
            and date(x["history"]["first_seen_at"]) >= start
        )
        for x in current
    )
    available = prior_count is not None
    delta = len(current) - prior_count if available else None
    return {
        "current_count": len(current),
        "prior_count": prior_count,
        "delta": delta,
        "newly_observed_count": newly,
        "period_start": start.isoformat(),
        "period_end": now.isoformat(),
        "comparison_start": (start - timedelta(days=7)).isoformat(),
        "comparison_end": start.isoformat(),
        "available": available,
        "reason": None if available else "INSUFFICIENT_HISTORY",
    }


def fixture(now: datetime):
    def o(i, title, kind, n, days, agency="Department of Defense"):
        x = {
            "canonical_source_id": i,
            "source": "SAM",
            "opportunity_id": i,
            "title": title,
            "agency": agency,
            "office": "Sample procurement office",
            "posted_date": (now - timedelta(days=3)).isoformat(),
            "response_deadline": (now + timedelta(days=days)).isoformat(),
            "notice_type": kind,
            "notice_category": normalize_notice_type(kind)[0],
            "stage": procurement_stage(kind),
            "sources_sought": normalize_notice_type(kind)[1],
            "set_aside": "Total Small Business",
            "naics": n,
            "description": "SAMPLE fixture synopsis.",
            "source_payload": {
                "title": title,
                "type": kind,
                "description": "SAMPLE fixture synopsis.",
                "naicsCode": n,
            },
            "source_revision": f"sample-{i}-v1",
            "official_source_url": f"https://sam.gov/opp/{i}",
            "evidence": {"id": f"sample-{i}", "collected_at": now.isoformat()},
            "freshness": {"collected_at": now.isoformat()},
            "history": {
                "first_seen_at": (
                    now - timedelta(days=2 if i == "SAM-1" else 10)
                ).isoformat(),
                "last_seen_at": now.isoformat(),
            },
            "data_mode": "SAMPLE",
            "naics_targeting": "VERIFIED",
            "market": market_for(n, agency),
            "btx_context": {
                "state": "SAMPLE",
                "data_mode": "SAMPLE",
                "aligned": i == "SAM-1",
                "business_unit": "Precision Components",
            },
            "missingness": [],
        }
        x["relevance"] = relevance(x, now=now)
        return x

    opp = [
        o(
            "SAM-1",
            "Aerospace precision component sources sought",
            "Sources Sought",
            "336413",
            21,
        ),
        o(
            "SAM-2",
            "Semiconductor package solicitation",
            "Solicitation",
            "334413",
            7,
            "Department of Energy",
        ),
        o(
            "SAM-3",
            "Unresolved special notice",
            "Special Notice",
            "999999",
            2,
            "Unknown Agency",
        ),
    ]
    aw = []
    for i, r, a, d, n in (
        ("AWD-1", "BTX Sample Prime", "1200000", "2026-02-15", "336413"),
        ("AWD-2", "BTX Sample Prime", "800000", "2025-02-15", "336413"),
        ("AWD-3", "Sample Semiconductor Co", "500000", "2026-05-10", "334413"),
    ):
        dt = date(d)
        fy, fq = fiscal(dt)
        aw.append(
            {
                "canonical_source_id": i,
                "source": "USASPENDING",
                "award_id": i,
                "recipient": r,
                "award_amount": a,
                "award_date": dt.isoformat(),
                "fiscal_year": fy,
                "fiscal_quarter": fq,
                "naics": n,
                "awarding_agency": "Department of Defense",
                "description": "SAMPLE award fixture",
                "official_source_url": f"https://www.usaspending.gov/award/{i}",
                "evidence": {"id": f"sample-{i}", "collected_at": now.isoformat()},
                "freshness": {"collected_at": now.isoformat()},
                "data_mode": "SAMPLE",
                "market": market_for(n, "Department of Defense"),
                "canonical_customer": {"state": "SAMPLE", "name": r}
                if r == "BTX Sample Prime"
                else None,
                "missingness": [],
            }
        )
    return opp, aw


def procurement_projection(runtime: Any, **filters: Any) -> dict:
    now = runtime.observed_at()
    verified = runtime.settings.monitor_sam_naics_verification_state == "VERIFIED"
    verified_naics = {
        code.strip()
        for code in getattr(runtime.settings, "monitor_sam_naics", "").split(",")
        if code.strip()
    }
    opp = []
    aw = []
    from btx_omni.monitor.service import current_source_observations

    for obs in current_source_observations(runtime.monitor):
        try:
            p = json.loads(obs.structured_payload or "{}")
        except json.JSONDecodeError:
            continue
        if obs.source_identity.source_system == "sam_gov":
            opp.append(opportunity(p, obs, verified=verified))
        elif obs.source_identity.source_system == "usaspending":
            projected_award = award(p, obs)
            # Recipient targeting establishes account identity, not manufacturing
            # relevance. Once a governed NAICS scope is enabled, keep award
            # analytics inside that same explicit scope.
            if not verified or projected_award.get("naics") in verified_naics:
                aw.append(projected_award)
    if getattr(runtime.settings, "federal_procurement_fixture_mode", False):
        opp, aw = fixture(now)
    for x in opp:
        x.setdefault("relevance", relevance(x, now=now))
        repository = getattr(getattr(runtime, "monitor", None), "repository", None)
        x["governed_explanation"] = persisted_seller_explanation(
            repository,
            subject_key=federal_opportunity_subject_key(x),
            explanation_type=ExplanationType.FEDERAL_OPPORTUNITY_RELEVANCE,
        )
    partnerships: set[str] = set()
    try:
        partnerships = {
            item["account_id"]
            for item in runtime.account_planning.view("federal-projection")[
                "strategic_partnerships"
            ]
        }
    except (AttributeError, KeyError):
        pass
    assessments: dict[str, dict] = {}
    repository = getattr(getattr(runtime, "monitor", None), "repository", None)
    persisted = {
        row["opportunity_id"]: row
        for row in (repository.current_federal_assessments() if repository else ())
    }
    environment = (
        runtime.environment()
        if callable(getattr(runtime, "environment", None))
        else getattr(runtime, "sample", None)
    )
    if environment:
        for item in opp:
            assessment = build_assessment(
                item, environment=environment, awards=aw,
                partnerships=partnerships, now=now,
            )
            durable = persisted.get(item["opportunity_id"])
            if repository and (
                durable is None or durable["input_revision"] != assessment["input_revision"]
            ):
                durable = repository.persist_federal_assessment(assessment, now=now)
            if durable:
                assessment = {
                    **durable["projection"],
                    "assessment_id": durable["id"],
                    "assessment_version": durable["version"],
                }
            else:
                assessment = {
                    **assessment,
                    "assessment_id": hashlib.sha256(
                        f"{assessment['opportunity_id']}|{assessment['input_revision']}".encode()
                    ).hexdigest(),
                    "assessment_version": 1,
                }
            assessments[item["opportunity_id"]] = assessment
            item["assessment"] = assessment

    def ok(x):
        days = (
            (date(x.get("response_deadline")) - now).days
            if x.get("response_deadline")
            else None
        )
        bucket = filters.get("deadline_bucket")
        return (
            (
                not filters.get("notice_type")
                or x["notice_category"] == filters["notice_type"]
            )
            and (
                filters.get("sources_sought") is None
                or x["sources_sought"] == filters["sources_sought"]
            )
            and (not filters.get("naics") or x["naics"] == filters["naics"])
            and (not filters.get("set_aside") or x["set_aside"] == filters["set_aside"])
            and (not filters.get("sector") or x["market"] == filters["sector"])
            and (
                filters.get("minimum_relevance") is None
                or x["relevance"]["score"] >= filters["minimum_relevance"]
            )
            and (
                not bucket
                or bucket == "14_DAYS"
                and days is not None
                and 0 <= days <= 14
                or bucket == "30_DAYS"
                and days is not None
                and 0 <= days <= 30
            )
        )

    active = sorted(
        [
            x
            for x in opp
            if ok(x)
            and x.get("stage", {}).get("code")
            not in {"AWARD", "INACTIVE"}
            and (not x.get("response_deadline") or date(x["response_deadline"]) >= now)
        ],
        key=lambda x: (
            -x["relevance"]["score"],
            x.get("response_deadline") or "9999",
            x["opportunity_id"],
        ),
    )
    fy = filters.get("fiscal_year") or max(
        (x["fiscal_year"] for x in aw if x["fiscal_year"]), default=None
    )
    scope = [x for x in aw if x["fiscal_year"] == fy]
    total = sum(
        (Decimal(x["award_amount"]) for x in scope if x.get("award_amount")), Decimal()
    )
    secs = defaultdict(Decimal)
    qs = defaultdict(Decimal)
    recs = defaultdict(Decimal)
    for x in scope:
        if x.get("award_amount"):
            secs[x["market"]] += Decimal(x["award_amount"])
            recs[x["recipient"]] += Decimal(x["award_amount"])
    for x in aw:
        if x.get("award_amount"):
            qs[(x["fiscal_year"], x["fiscal_quarter"], x["market"])] += Decimal(
                x["award_amount"]
            )
    return {
        "sam": {
            "state": "SAMPLE"
            if getattr(runtime.settings, "federal_procurement_fixture_mode", False)
            else "CONNECTED"
            if opp
            else "NOT_CONFIGURED"
            if not runtime.settings.sam_api_key
            else "NO_DATA",
            "targeting": "VERIFIED"
            if verified
            or getattr(runtime.settings, "federal_procurement_fixture_mode", False)
            else "PENDING_CONFIRMATION",
            "coverage": (
                list(repository.procurement_coverage())
                if repository else []
            ),
            "coverage_complete": (
                bool(repository.procurement_coverage())
                and all(not item["pending_continuation"] for item in repository.procurement_coverage())
                if repository else False
            ),
            "coverage_note": "Collected counts describe the saved search windows, not the total federal market.",
        },
        "usaspending": {
            "state": "SAMPLE"
            if getattr(runtime.settings, "federal_procurement_fixture_mode", False)
            else "CONNECTED"
            if aw
            else "NO_DATA",
            "scope": "SAMPLE_FIXTURE"
            if getattr(runtime.settings, "federal_procurement_fixture_mode", False)
            else "PROVISIONAL_UNSCOPED"
            if not verified
            else "VERIFIED_NAICS_SCOPE",
        },
        "active": {
            "kpis": {
                "open_opportunities": len(active),
                "posted_last_7_days": sum(
                    date(x["posted_date"]) >= now - timedelta(days=7) for x in active
                ),
                "closing_within_14_days": sum(
                    0 <= (date(x["response_deadline"]) - now).days <= 14
                    for x in active
                    if x.get("response_deadline")
                ),
                "sources_sought": sum(x["sources_sought"] for x in active),
            },
            "opportunities": active,
            "sector_breakdown": [
                {"sector": m, "count": sum(x["market"] == m for x in active)}
                for m in (*MARKETS, "UNRESOLVED")
            ],
            "history": "INSUFFICIENT_HISTORY",
            "pipeline": [
                dict(
                    {
                        "type": n,
                        "count": sum(x["notice_category"] == n for x in active),
                    },
                    **period_comparison(
                        [x for x in active if x["notice_category"] == n], now=now
                    ),
                )
                for n in NOTICE.values()
            ],
            "filter_options": {
                "naics": sorted({x["naics"] for x in opp if x["naics"]}),
                "set_asides": sorted({x["set_aside"] for x in opp if x["set_aside"]}),
            },
        },
        "awarded": {
            "awards": aw,
            "available_fiscal_years": sorted(
                {x["fiscal_year"] for x in aw if x["fiscal_year"]}, reverse=True
            ),
            "selected_fiscal_year": fy,
            "kpis": {"total_award_amount": str(total), "yoy_percent": None},
            "sector_totals": [
                {
                    "sector": m,
                    "amount": str(a),
                    "share": str((a / total * 100).quantize(Decimal(".01")))
                    if total
                    else None,
                }
                for m, a in sorted(secs.items())
            ],
            "quarterly": [
                {
                    "fiscal_year": a,
                    "quarter": b,
                    "sector": c,
                    "total_award_amount": str(d),
                }
                for (a, b, c), d in sorted(qs.items())
            ],
            "top_recipients": [
                {"recipient": a, "total_award_amount": str(b), "yoy_delta": None}
                for a, b in sorted(recs.items(), key=lambda x: (-x[1], x[0]))
            ],
            "lag": {
                "state": "INSUFFICIENT_HISTORY",
                "detail": "Award records do not include a downstream milestone or delivery date.",
            },
        },
    }


def federal_assessments_for_account(runtime: Any, account_id: str) -> list[dict]:
    """Return canonical persisted routes for one organization without rebuilding them."""
    repository = getattr(getattr(runtime, "monitor", None), "repository", None)
    if repository is None:
        return []
    result = []
    for row in repository.current_federal_assessments():
        assessment = row["projection"]
        routes = [
            route for route in assessment.get("routes", ())
            if route.get("account_id") == account_id
        ]
        if routes:
            result.append({
                **assessment,
                "assessment_id": row["id"],
                "assessment_version": row["version"],
                "account_routes": routes,
            })
    return sorted(
        result,
        key=lambda item: (
            -max(route["score"] for route in item["account_routes"]),
            item["opportunity_id"],
        ),
    )


def federal_today_candidates(runtime: Any, *, limit: int = 5) -> list[dict]:
    """Time-sensitive persisted routes only; collection counts never drive priority."""
    repository = getattr(getattr(runtime, "monitor", None), "repository", None)
    if repository is None:
        return []
    candidates = []
    for row in repository.current_federal_assessments():
        assessment = row["projection"]
        route = assessment.get("recommended_route")
        if not route or route.get("score", 0) < 55:
            continue
        stage = assessment.get("stage", {}).get("code")
        if stage not in {"SOURCES_SOUGHT", "PRE_SOLICITATION", "SOLICITATION"}:
            continue
        candidates.append({
            "assessment_id": row["id"],
            "assessment_version": row["version"],
            "opportunity_id": row["opportunity_id"],
            "stage": assessment["stage"],
            "route": route,
            "durability": assessment.get("durability"),
        })
    return sorted(candidates, key=lambda item: (-item["route"]["score"], item["opportunity_id"]))[:limit]
