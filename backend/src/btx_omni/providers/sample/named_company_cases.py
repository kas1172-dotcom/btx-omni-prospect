"""Clearly simulated named-company account exercises, separate from public research."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.programs import ComponentClass, Program
from btx_omni.modules.commercial.ledger import KEYS, validate_commercial_account
from btx_omni.providers.sample.boeing_pursuit import add_boeing_pursuit
from btx_omni.providers.sample.classifications import (
    authored_bin_row,
    authored_input_row,
)
from btx_omni.providers.sample.enhancement import (
    add_boeing_financials,
    boeing_recovery,
    reconcile_months,
    synthetic_record,
)

SOURCE = "Authored SAMPLE commercial record; simulated, not a BTX or buyer fact"
SCOPE_SOURCE = "Authored SAMPLE scope requirements; simulated, not buyer-stated"

# All names are canonical identities; every relationship, financial amount,
# pursuit, and capability requirement below is a SAMPLE scenario assumption.
CUSTOMERS = {
    "lockheed-martin": ("Lockheed Martin", "era-wheeling", "F-35 Lightning II SAMPLE component exercise", 25,
                        "EDM", "17-4PH", "standard aerospace (>= +/-0.001 in)", "AS9100D"),
    "northrop-grumman": ("Northrop Grumman", "era-arizona", "NASA VADR SAMPLE component exercise", 10,
                         "5-axis milling", "7075-T6", "standard aerospace (>= +/-0.002 in)", "AS9100D"),
}
PURSUITS = {
    "ge-aerospace": ("GE Aerospace", "era-elk-grove", "NASA EPFD SAMPLE pursuit", 8,
                     "5-axis milling", "7075-T6", "standard aerospace (>= +/-0.001 in)", "AS9100D"),
    "anduril-industries": ("Anduril Industries", "era-arizona", "Counter-UAS SAMPLE pursuit", 5,
                           "5-axis milling", "7075-T6", "standard aerospace (>= +/-0.002 in)", "AS9100D"),
    "blue-origin": ("Blue Origin", "era-elk-grove", "NASA VADR SAMPLE pursuit", 10,
                    "5-axis milling", "7075-T6", "standard aerospace (>= +/-0.001 in)", "AS9100D"),
    "rocket-lab-usa": ("Rocket Lab USA", "era-wheeling", "NASA VADR SAMPLE pursuit", 10,
                       "EDM", "17-4PH", "standard aerospace (>= +/-0.001 in)", "AS9100D"),
    "applied-materials": ("Applied Materials", "a1j-san-jose", "Semiconductor equipment SAMPLE pursuit", 15,
                          "milling", "6061-T6", "standard precision (>= +/-0.001 in)", "ISO 9001"),
    "medtronic": ("Medtronic", "apm-rochester", "Medical device prototype SAMPLE pursuit", 8,
                  "Swiss turning", "Ti-6Al-4V", "prototype precision (>= +/-0.0002 in)", "ISO 9001"),
}
PRE_PURSUIT = ("intel", "tsmc-arizona", "symbotic")
EXISTING_PROGRAMS = {
    "lockheed-martin": "f-35-lightning-ii",
    "applied-materials": "amat-sym3-etch",
    "medtronic": "medtronic-hugo",
}

SCALE = {  # Uniformly simulated; not drawn from public financial statements.
    "ge-aerospace": 2_000_000_000, "anduril-industries": 500_000_000,
    "blue-origin": 500_000_000, "rocket-lab-usa": 200_000_000,
    "applied-materials": 2_000_000_000, "medtronic": 2_000_000_000,
    "intel": 2_000_000_000, "tsmc-arizona": 500_000_000, "symbotic": 100_000_000,
}

# These are explicitly authored scenario assumptions, never claims about an
# actual award, staffing action, procurement process, or BTX relationship.
PATH_B_OVERRIDES = {
    "lockheed-martin": {
        "program_durability.repeat_production_pattern": "ESTABLISHED_RECURRING",
        "program_momentum.production_delivery_milestones": "ON_TRACK",
    },
    "northrop-grumman": {
        "program_durability.repeat_production_pattern": "MULTIPLE_BATCHES_NOT_LOCKED",
        "program_momentum.recent_awards_funding_production_increases": "SOME_POSITIVE",
        "program_momentum.production_delivery_milestones": "ON_TRACK",
    },
    "ge-aerospace": {
        "program_durability.commitment_strength": "BUDGETED_CREDIBLE_FUNDING",
        "program_momentum.production_delivery_milestones": "ON_TRACK",
    },
    "anduril-industries": {
        "program_durability.commitment_strength": "EARLY_STAGE_CONDITIONAL",
        "program_durability.industry_specific_maturity_evidence": "WEAK_EARLY",
        "program_momentum.recent_awards_funding_production_increases": "NO_MATERIAL_CHANGE",
        "program_momentum.production_delivery_milestones": "NONE_IDENTIFIED",
        "strategic_target_fit": "PLAUSIBLE_UNCLEAR",
    },
    "blue-origin": {
        "program_durability.commitment_strength": "EARLY_STAGE_CONDITIONAL",
        "program_momentum.production_delivery_milestones": "NONE_IDENTIFIED",
    },
    "rocket-lab-usa": {
        "program_durability.commitment_strength": "EARLY_STAGE_CONDITIONAL",
        "program_durability.industry_specific_maturity_evidence": "WEAK_EARLY",
        "addressable_btx_work.repeat_volume_potential": "ONE_OFF",
        "program_momentum.recent_awards_funding_production_increases": "NO_MATERIAL_CHANGE",
        "program_momentum.production_delivery_milestones": "NONE_IDENTIFIED",
        "strategic_target_fit": "PLAUSIBLE_UNCLEAR",
    },
    "applied-materials": {
        "program_durability.commitment_strength": "BUDGETED_CREDIBLE_FUNDING",
        "program_momentum.production_delivery_milestones": "ON_TRACK",
        "strategic_target_fit": "PLAUSIBLE_UNCLEAR",
    },
    "medtronic": {
        "program_durability.commitment_strength": "BUDGETED_CREDIBLE_FUNDING",
        "program_momentum.recent_awards_funding_production_increases": "NO_MATERIAL_CHANGE",
        "program_momentum.production_delivery_milestones": "ON_TRACK",
    },
}

# These are distinct, explicitly simulated pursuit assumptions, not claims
# about actual buyers, bid positions, prior BTX work, or site commitments.
# The facility-derived delivery factors remain Path A and are never set here.
PURSUIT_INPUTS = {
    "lockheed-martin": {
        "pwin": ("DECISION_AUTHORITY_TWO_WAY", "ELIGIBLE_INCUMBENT", 9, 10,
                 "BUDGET_DATE_CONFIRMED", 105_000, "TWO_ACCEPTED_SAME_REQUIREMENTS"),
        "delivery": (35, 72_000, "ALL_OWNERS_AND_DATES"),
        "load": (200, 220),
        "story": "Mature renewal exercise: two-way decision access and repeated accepted same-family deliveries.",
    },
    "northrop-grumman": {
        "pwin": ("EVALUATION_COMMITTEE_TWO_WAY", "INVITED_BIDDER", 8, 10,
                 "BUDGET_DATE_CONFIRMED", 100_000, "ONE_ACCEPTED_SAME_REQUIREMENTS"),
        "delivery": (21, 78_000, "ONE_DATE_UNKNOWN"),
        "load": (490, 550),
        "story": "Growing relationship exercise: committee access, one accepted same-family delivery, one date open.",
    },
    "ge-aerospace": {
        "pwin": ("NAMED_INFLUENCER", "INVITED_BIDDER", 8, 10,
                 "BUDGET_DATE_CONFIRMED", 97_000, "ACCEPTED_ADJACENT_FAMILY"),
        "delivery": (30, 80_000, "ONE_DATE_UNKNOWN"),
        "load": (1_060, 1_200),
        "story": "Warm funded-program what-if: influencer contact, adjacent-family reference, and prepositioned material; not actual BTX sales.",
    },
    "anduril-industries": {
        "pwin": ("VERIFIED_ROLE_NO_INTERACTION", "UNSOLICITED_CHALLENGER", 6, 10,
                 "CONDITIONAL_BUDGET", 90_000, "CONFIRMED_NONE"),
        "delivery": (14, 94_000, "ONE_OWNER_UNKNOWN"),
        "load": (660, 740),
        "story": "Cold challenger exercise: conditional funding, staged material, and a tight Arizona work-center window.",
    },
    "blue-origin": {
        "pwin": ("NAMED_INFLUENCER", "INVITED_BIDDER", 7, 10,
                 "BUDGET_DATE_CONFIRMED", 95_000, "VALIDATED_PROTOTYPE"),
        "delivery": (10, 86_000, "ALL_OWNERS_AND_DATES"),
        "load": (1_155, 1_300),
        "story": "Emerging launch pursuit exercise: prototype reference and tight Elk Grove load.",
    },
    "rocket-lab-usa": {
        "pwin": ("VERIFIED_ROLE_NO_INTERACTION", "UNSOLICITED_CHALLENGER", 5, 10,
                 "CONDITIONAL_BUDGET", 85_000, "CONFIRMED_NONE"),
        "delivery": (30, 101_000, "MULTIPLE_OWNERS_UNKNOWN"),
        "load": (255, 288),
        "story": "Capacity-constrained edge-of-fit exercise: stocked material but negative modeled margin and unresolved owners.",
    },
    "applied-materials": {
        "pwin": ("NAMED_INFLUENCER", "INVITED_BIDDER", 8, 10,
                 "BUDGET_CONFIRMED", 100_000, "ACCEPTED_ADJACENT_FAMILY"),
        "delivery": (30, 78_000, "ONE_DATE_UNKNOWN"),
        "load": (620, 700),
        "story": "Equipment-adjacent what-if: influencer access, prepositioned material, and a solid modeled margin.",
    },
    "medtronic": {
        "pwin": ("EVALUATION_COMMITTEE_TWO_WAY", "INVITED_BIDDER", 7, 10,
                 "BUDGET_DATE_CONFIRMED", 105_000, "VALIDATED_PROTOTYPE"),
        "delivery": (14, 94_000, "ONE_DATE_UNKNOWN"),
        "load": (1_060, 1_200),
        "story": "Prototype-stage medical exercise: committee access, not accepted production work.",
    },
}


def _clone_boeing_shape(aid: str, name: str, *, financials: bool, anchor=None) -> dict:
    # Clone into a new object; the Boeing fixture and its golden assertions are
    # never mutated. Reuse the already-reconciled SAMPLE transaction shape.
    source = boeing_recovery(anchor=anchor)
    if financials:
        add_boeing_financials(source)
    add_boeing_pursuit(source)
    account = json.loads(json.dumps(source).replace("boeing", aid).replace("Boeing", name)
        .replace(f"demo:j7:{aid}:", f"sample:{aid}:pursuit:")
        .replace("recovery-expansion", "component-opportunity"))
    account["identity"]["display_name"] = name + " — SAMPLE scenario"
    for collection in KEYS:
        for row in account[collection]:
            row.setdefault("source", SOURCE)
    for row in account["opportunities"]:
        row["qualification_evidence"].setdefault("source", SOURCE)
        for observation in row["score_observations"]:
            observation.setdefault("source", SOURCE)
        for family in row["scoring_inputs"].values():
            for factor in family.values():
                factor.setdefault("source", SOURCE)
    return account


def _scope(opportunity: dict, config: tuple, *, as_of: str) -> None:
    _, facility_id, _, _, process, material, tolerance, cert = config
    opportunity["delivery_facility_id"] = facility_id
    opportunity["scope_requirements"] = {
        "required_certifications": [cert], "required_processes": [process],
        "required_materials": [material], "required_tolerance_band": tolerance,
        "expected_volume_next_12m": 240, "expected_hours_per_unit": 4.5,
        "required_hours_next_90d": 270, "required_by_date": "2027-03-31",
        "data_mode": "SAMPLE", "synthetic": True, "source": SCOPE_SOURCE,
        "note": "Hours and volume are simulated comparison assumptions, not buyer requirements.",
    }
    for factor in opportunity["scoring_inputs"]["delivery_feasibility"].values():
        factor["facility_id"] = facility_id
    opportunity["title"] = f"SAMPLE {config[0]} component pursuit — not a verified buyer opportunity"
    opportunity["business_context"] = (
        f"Authored {as_of} SAMPLE scenario; no actual award, quote, buyer contact, "
        "capacity promise, or commercial transaction is asserted."
    )
    opportunity["material_uncertainties"] = ["Verify actual sourcing need, buyer authority, and site qualification."]


def _author_path_b(opportunity: dict, aid: str, name: str, *, as_of: str) -> None:
    note = f"Authored SAMPLE scoring assumption for {name}; not verified company or BTX evidence."
    path_a = {"program_durability.expected_production_horizon", "btx_commercial_adjacency",
        "addressable_btx_work.cross_bu_applicability",
        "addressable_btx_work.btx_relevant_component_content",
        "btx_manufacturing_fit.material_match", "btx_manufacturing_fit.process_tolerance_match",
        "btx_manufacturing_fit.certification_compliance_fit",
        "btx_manufacturing_fit.volume_compatibility"}
    # The cloned shape supplies a convenient 18-leaf schema, but no authored
    # value survives for a Path A leaf. Projection derives all eight afresh.
    opportunity["score_observations"] = [row for row in opportunity["score_observations"]
                                          if row["path"] not in path_a]
    for row in opportunity["score_observations"]:
        value = PATH_B_OVERRIDES.get(aid, {}).get(row["path"], row["bin"])
        row.update(authored_bin_row(opportunity_id=opportunity["opportunity_id"], path=row["path"],
            bin_value=value, as_of=as_of, evidence_ids=(opportunity["opportunity_id"],), note=note))
        row["source"] = SOURCE
    for factor in ("capability_match", "schedule_feasibility", "quality_certification"):
        opportunity["scoring_inputs"]["delivery_feasibility"].pop(factor)
    if aid not in CUSTOMERS:
        # A cold prospect is not an incumbent, even in a synthetic pursuit.
        value = "INVITED_BIDDER" if aid == "ge-aerospace" else "UNSOLICITED_CHALLENGER"
        opportunity["scoring_inputs"]["pwin"]["competitive_position"] = {
            **authored_input_row(opportunity_id=opportunity["opportunity_id"], family="pwin",
                factor="competitive_position", raw={"state": value},
                facility_id=opportunity["delivery_facility_id"], as_of=as_of, note=note),
            "source": SOURCE,
        }


def _differentiate_pursuit(account: dict, opportunity: dict, aid: str, *, as_of: str) -> None:
    """Author narrative-specific raw inputs; Path A delivery fields stay derived."""
    config = PURSUIT_INPUTS[aid]
    access, position, met, total, budget, target, track = config["pwin"]
    material_days, cost, coordination = config["delivery"]
    volume, required_hours = config["load"]
    scope = opportunity["scope_requirements"]
    scope.update(expected_volume_next_12m=volume, required_hours_next_90d=required_hours,
                 note=(f"{config['story']} Annual units, hours per unit, and 90-day hours "
                       "are derived SAMPLE planning assumptions, not buyer-stated requirements."))
    oid, facility_id = opportunity["opportunity_id"], opportunity["delivery_facility_id"]
    note = f"{config['story']} Authored SAMPLE scoring input, not verified company or BTX evidence."
    pwin = {
        "buyer_access": {"state": access},
        "competitive_position": {"state": position},
        "requirement_fit": {"critical_requirements_pass": True,
                            "noncritical_met": met, "noncritical_total": total},
        "budget_process": {"state": budget},
        "price_competitiveness": {"quoted_minor": 100_000, "buyer_target_minor": target},
        "track_record": {"state": track},
    }
    delivery = {
        "material_readiness": {"most_constrained_critical_material_days_early": material_days},
        "margin": {"quoted_minor": 100_000, "estimated_total_cost_minor": cost},
        "coordination": {"state": coordination},
    }
    for family, factors in (("pwin", pwin), ("delivery_feasibility", delivery)):
        for factor, raw in factors.items():
            opportunity["scoring_inputs"][family][factor] = {
                **authored_input_row(opportunity_id=oid, family=family, factor=factor,
                    raw=raw, facility_id=facility_id, as_of=as_of, note=note),
                "source": SOURCE,
            }
    # The fictional interaction evidence mirrors the authored access tier;
    # it does not assert that a real contact or conversation occurred.
    for interaction in account["interactions"]:
        if oid in interaction.get("related_record_ids", ()):
            interaction.update(
                meaningful_touch=access != "VERIFIED_ROLE_NO_INTERACTION",
                two_way=(access in {"DECISION_AUTHORITY_TWO_WAY", "EVALUATION_COMMITTEE_TWO_WAY"}
                         or aid == "applied-materials"),
                notes=f"{config['story']} Fictional SAMPLE role interaction only; no verified real contact.",
                source=SOURCE,
            )


def _customer(aid: str, config: tuple, *, anchor=None) -> dict:
    name = config[0]
    account = _clone_boeing_shape(aid, name, financials=True, anchor=anchor)
    prefix = f"sample:{aid}:pursuit:"
    if aid in EXISTING_PROGRAMS:
        account = json.loads(json.dumps(account).replace(prefix + "program", EXISTING_PROGRAMS[aid]))
    # The four accepted historical SAMPLE releases are retained. The Boeing
    # J7 partial dispatch and open inspection issue are not copied as facts
    # about either other company.
    for collection, field in (("orders", "order_id"), ("order_lines", "order_line_id"),
                              ("shipments", "shipment_id"), ("service_events", "service_event_id"),
                              ("fulfillment_plans", "plan_id"), ("actions", "action_id")):
        account[collection] = [row for row in account[collection]
                               if not row[field].startswith(prefix)]
    account["programs"][0].update(
        name=config[2], expected_production_horizon_years=config[3], source=SOURCE,
        description="Synthetic component scope associated with a named program for demo only; not a supply claim.")
    account["components"][0].update(name="SAMPLE precision component", source=SOURCE)
    for quote in account["quotes"]:
        if quote["quote_id"] == prefix + "quote":
            quote["status"] = "OPEN"
    if aid == "northrop-grumman":
        account["service_events"] = []
        for payment in account["payments"]:
            invoice = next(row for row in account["invoices"] if row["invoice_id"] == payment["invoice_id"])
            payment["paid_date"] = min(invoice["due_date"], account["as_of"])
    else:
        # Stable relationship: one resolved, noncritical historical review.
        account["service_events"] = account["service_events"][:1]
    # Removing Boeing's unrelated September J7 order must not silently turn
    # either named customer's recovery/stability exercise into a zero-booking
    # month. This is a new, unshipped SAMPLE release, not a claimed real order.
    release = f"sample:{aid}:release:12"
    order_on = date.fromisoformat(account["as_of"])
    quote_on = order_on - timedelta(days=1)
    received_on = order_on - timedelta(days=2)
    component_id = account["components"][0]["component_id"]
    program_id = account["programs"][0]["program_id"]
    quantity, unit_price = 240, 100_000
    value = quantity * unit_price
    def add(collection: str, **row):
        account[collection].append(synthetic_record(**row, source=SOURCE))
    add("rfqs", rfq_id=release + ":rfq", received_date=received_on.isoformat(),
        notes="Synthetic account release; no actual buyer request.")
    add("quotes", quote_id=release + ":quote", rfq_id=release + ":rfq",
        current_revision_id=release + ":revision", status="WON", decision_due_date=order_on.isoformat())
    add("quote_lines", quote_line_id=release + ":quote-line",
        quote_revision_id=release + ":revision", component_id=component_id,
        quantity=quantity, unit_price_minor=unit_price, line_total_minor=value,
        technical_requirements="Synthetic recurring lot; not a buyer drawing.")
    add("quote_revisions", quote_revision_id=release + ":revision",
        quote_id=release + ":quote", revision_number=1, issued_date=quote_on.isoformat(),
        supersedes_revision_id=None, line_ids=[release + ":quote-line"], total_minor=value)
    add("orders", order_id=release + ":order", quote_id=release + ":quote",
        accepted_quote_revision_id=release + ":revision", agreement_id=None,
        ordered_date=order_on.isoformat(), line_ids=[release + ":order-line"],
        total_minor=value, status="OPEN")
    add("order_lines", order_line_id=release + ":order-line", order_id=release + ":order",
        component_id=component_id, program_id=program_id, business_unit_id="BU-ERA",
        quantity=quantity, unit_price_minor=unit_price, unit_cost_minor=70_000,
        line_total_minor=value, committed_date=(order_on + timedelta(days=180)).isoformat())
    account["monthly_commercial_history"] = []
    reconcile_months(account)
    for month in account["monthly_commercial_history"]:
        month["source"] = SOURCE
        for allocation in month["business_unit_allocations"]:
            allocation["source"] = SOURCE
    account["ttm_summary"]["source"] = SOURCE
    account["commercial_case"]["source"] = SOURCE
    account["bu_revenue_exposure"]["account_revenue_minor"] = account["ttm_summary"]["revenue_minor"]
    opportunity = account["opportunities"][0]
    _scope(opportunity, config, as_of=account["as_of"])
    _author_path_b(opportunity, aid, name, as_of=account["as_of"])
    _differentiate_pursuit(account, opportunity, aid, as_of=account["as_of"])
    account["source"] = SOURCE
    validate_commercial_account(account)
    return account


def _provenance(identity: str, as_of: str) -> Provenance:
    observed = datetime.combine(date.fromisoformat(as_of), datetime.min.time(), UTC)
    return Provenance("named-company-sample", identity, f"sample://named-company/{identity}",
        observed, observed, Classification.INTERNAL_COMMERCIAL, EvidenceState.INFERRED,
        DataMode.SAMPLE, True)


def _prospect_evidence(aid: str, *, as_of: str) -> dict[str, dict]:
    cohort = "PRIMARY" if aid == "ge-aerospace" else "EXPLORATORY" if aid in PRE_PURSUIT else "ADJACENT"
    states = {
        "target_cohort_match": cohort,
        "manufacturing_fit": "ONE_MATCHING_SITE" if aid in PURSUITS else "COMPONENT_ADJACENCY",
        "outsourcing_posture": "MIXED",
        "strategic_archetype": "OEM_PRIME_BUYING_AUTHORITY" if aid not in {"symbotic", "applied-materials"} else "COMPONENT_MANUFACTURER",
        "existing_btx_access": "RESEARCHED_NO_ACCESS",
    }
    rows = {key: {"state": value} for key, value in states.items()}
    rows["scale"] = {"organization_ttm_revenue_usd": SCALE[aid]}
    return {key: {
        **raw, "account_id": aid, "evidence_ids": [f"sample:{aid}:prospect-fit:{key}"],
        "source_urls": [f"sample://named-company/{aid}/prospect-fit"],
        "review_state": "VERIFIED", "reviewed_as_of": as_of,
        "reason": "Reviewed authored SAMPLE assumption; not public revenue, sourcing evidence, or buyer access.",
        "data_mode": "SAMPLE", "synthetic": True,
        "source": "Authored SAMPLE prospect-fit record; simulated scale and relationship",
        "provenance": {"data_mode": "SAMPLE", "synthetic": True, "truth_class": "POC_SCENARIO"},
    } for key, raw in rows.items()}


def _prospect_pursuit(aid: str, config: tuple, *, anchor=None) -> tuple[dict, Program | None, ComponentClass]:
    name = config[0]
    account = _clone_boeing_shape(aid, name, financials=False, anchor=anchor)
    if aid in EXISTING_PROGRAMS:
        account = json.loads(json.dumps(account).replace(f"sample:{aid}:pursuit:program", EXISTING_PROGRAMS[aid]))
    opportunity = account["opportunities"][0]
    _scope(opportunity, config, as_of=account["as_of"])
    _author_path_b(opportunity, aid, name, as_of=account["as_of"])
    _differentiate_pursuit(account, opportunity, aid, as_of=account["as_of"])
    account["programs"][0].update(name=config[2], expected_production_horizon_years=config[3],
        description="Authored SAMPLE program association; not evidence of an actual award or BTX supply.", source=SOURCE)
    account["components"][0].update(name="SAMPLE scoped component", source=SOURCE)
    account["quotes"][0]["status"] = "OPEN"
    opportunity["source"] = SOURCE
    pursuit = {
        "account_id": aid, "as_of": account["as_of"],
        "opportunity": opportunity, "component": account["components"][0],
        "rfqs": account["rfqs"], "quotes": account["quotes"],
        "quote_revisions": account["quote_revisions"], "quote_lines": account["quote_lines"],
        "role_targets": account["role_targets"], "interactions": account["interactions"],
        "data_mode": "SAMPLE", "synthetic": True, "source": SOURCE,
        "provenance": {"data_mode": "SAMPLE", "synthetic": True, "truth_class": "POC_SCENARIO"},
    }
    program_id = opportunity["program_id"]
    component_id = opportunity["component_id"]
    program = None if aid in EXISTING_PROGRAMS else Program(program_id, aid, config[2], None,
        EvidenceState.INFERRED, _provenance(program_id, account["as_of"]),
        expected_production_horizon_years=config[3])
    facility_bu = {"era-elk-grove": "era-industries", "era-arizona": "era-industries",
                   "era-wheeling": "era-industries", "a1j-san-jose": "a1j-technologies",
                   "apm-rochester": "addison-precision"}[config[1]]
    component = ComponentClass(component_id, program_id, "SAMPLE scoped component",
        EvidenceState.INFERRED, _provenance(component_id, account["as_of"]),
        business_unit_ids=(facility_bu,))
    return pursuit, program, component


def add_named_company_cases(base, records: dict[str, dict], *, anchor=None):
    """Add two customer ledgers, six no-ledger pursuits, and three fit-only profiles."""
    as_of = date.fromisoformat(next(iter(records.values()))["as_of"]).isoformat()
    for aid, config in CUSTOMERS.items():
        records[aid] = _customer(aid, config, anchor=anchor)
    pursuits, programs, components = [], [], []
    for aid, config in PURSUITS.items():
        pursuit, program, component = _prospect_pursuit(aid, config, anchor=anchor)
        pursuits.append(pursuit)
        if program is not None:
            programs.append(program)
        components.append(component)
    accounts = tuple(replace(account, prospect_fit_evidence=_prospect_evidence(account.id, as_of=as_of))
                     if account.id in SCALE else account for account in base.accounts)
    return replace(base, accounts=accounts, programs=base.programs + tuple(programs),
                   component_classes=base.component_classes + tuple(components),
                   pursuits=tuple(pursuits))
