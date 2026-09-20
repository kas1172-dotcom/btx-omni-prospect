"""Source-bounded account planning gaps; unavailable targets stay unavailable."""

from __future__ import annotations


def sales_planning_gap(account: dict, *, canonical_account_id: str, revision: str) -> dict:
    summary = account["ttm_summary"]
    requirements = account.get("commercial_requirements") or {}
    target = requirements.get("sales_target_minor")
    if target is not None and (not isinstance(target, int) or target < 0):
        raise ValueError("Sales target must be a non-negative integer minor-unit value.")
    actual = summary.get("bookings_minor")
    if not isinstance(actual, int):
        actual = None
    shortfall = max(0, target - actual) if target is not None and actual is not None else None
    return {
        "account_id": canonical_account_id,
        "period": summary.get("period"),
        "currency": account["currency"],
        "actual_bookings_minor": actual,
        "target_bookings_minor": target,
        "shortfall_minor": shortfall,
        "status": "TARGET_UNAVAILABLE" if target is None else "ACTUAL_UNAVAILABLE" if actual is None else "SHORTFALL" if shortfall else "ON_OR_ABOVE_TARGET",
        "business_unit_ids": tuple(sorted({item["business_unit_id"] for item in account["components"]})),
        "evidence_ids": tuple(item["snapshot_id"] for item in account["monthly_commercial_history"]),
        "revision": revision,
        "interpretation": (
            "No approved sales target is recorded, so a sales shortfall cannot be calculated. Recorded TTM bookings remain available for planning context."
            if target is None
            else "Shortfall is target bookings less recorded TTM bookings, floored at zero; it is not a forecast."
        ),
    }
