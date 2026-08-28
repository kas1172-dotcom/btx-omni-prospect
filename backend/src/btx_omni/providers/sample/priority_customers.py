"""Bounded, explicitly simulated scenarios for Jamie's priority Customer cohort."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from btx_omni.core.classification import Classification
from btx_omni.domain.accounts import AccountRelationship
from btx_omni.domain.commercial import CommercialContext, MonthlyCommercialHistory
from btx_omni.providers.research._catalog_support import document, source_provenance


@dataclass(frozen=True)
class PriorityCustomerScenario:
    account_id: str
    sample_relationship: AccountRelationship
    reason_for_attention: str
    recommended_next_step: str
    scenario_intent: str
    simulated_score_inputs: dict[str, str]
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class PriorityCustomerImport:
    scenarios: dict[str, PriorityCustomerScenario]
    commercial_contexts: tuple[CommercialContext, ...]


def load_priority_customer_scenarios(
    *, account_ids: set[str], business_unit_ids: set[str]
) -> PriorityCustomerImport:
    payload = document("btx_sample_priority_customer_scenarios.json")
    scenarios: dict[str, PriorityCustomerScenario] = {}
    for row in payload["scenarios"]:
        account_id = str(row["account_id"])
        if account_id not in account_ids:
            raise ValueError(f"priority scenario references unknown Customer {account_id!r}")
        if account_id in scenarios:
            raise ValueError(f"duplicate priority scenario for {account_id!r}")
        scenarios[account_id] = PriorityCustomerScenario(
            account_id,
            AccountRelationship(str(row["sample_relationship"])),
            str(row["reason_for_attention"]),
            str(row["recommended_next_step"]),
            str(row["scenario_intent"]),
            {str(key): str(value) for key, value in row.get("score_inputs", {}).items()},
        )

    contexts: list[CommercialContext] = []
    for row in payload["commercial_contexts"]:
        account_id, business_unit_id = str(row["account_id"]), str(row["business_unit_id"])
        if account_id not in scenarios or business_unit_id not in business_unit_ids:
            raise ValueError("priority commercial context has an unknown foreign key")
        source_id = f"priority-context-{account_id}-{business_unit_id}"
        provenance_record = {
            "provenance": {
                "source_system": "priority-customer-sample",
                "source_record_id": source_id,
                "data_mode": "SAMPLE",
                "synthetic": True,
                "evidence_state": "CONFIRMED",
            }
        }
        provenance = source_provenance(
            provenance_record, classification=Classification.INTERNAL_COMMERCIAL
        )
        history = tuple(
            MonthlyCommercialHistory(
                date.fromisoformat(str(item["month"])),
                item.get("revenue_cents"),
                item.get("bookings_cents"),
                provenance,
            )
            for item in row["monthly"]
        )
        if not history:
            raise ValueError("priority commercial context requires monthly source rows")
        contexts.append(
            CommercialContext(
                account_id,
                business_unit_id,
                str(row["currency"]),
                sum(item.revenue_minor or 0 for item in history),
                sum(item.bookings_minor or 0 for item in history),
                str(row["customer_segment"]),
                str(row["end_market"]) if row.get("end_market") else None,
                None,
                None,
                date.fromisoformat(str(row["last_booking_date"])) if row.get("last_booking_date") else None,
                date.fromisoformat(str(row["last_order_date"])) if row.get("last_order_date") else None,
                history,
                provenance,
                jamie_validation_required=(
                    "SAMPLE commercial context for the priority-Customer POC; validate against connected BTX systems before action.",
                ),
            )
        )
    return PriorityCustomerImport(scenarios, tuple(contexts))
