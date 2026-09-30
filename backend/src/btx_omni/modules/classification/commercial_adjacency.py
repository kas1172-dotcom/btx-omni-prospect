"""Classify only evidenced active sales or quote-only adjacency."""

from datetime import date, timedelta

from btx_omni.modules.classification import SAMPLE_CLASSIFIER_RULE_VERSION
from btx_omni.modules.classification.contract import deterministic_bin

PATH = "btx_commercial_adjacency"


def classify_commercial_adjacency(account: dict, opportunity: dict, *, as_of: str):
    cutoff = date.fromisoformat(as_of) - timedelta(days=365)
    lines = {row["order_line_id"]: row for row in account.get("order_lines", ())}
    recent = [row for row in account.get("revenue_events", ()) if row["revenue_minor"] > 0
              and cutoff <= date.fromisoformat(row["recognized_date"]) <= date.fromisoformat(as_of)]
    units = {lines[row["order_line_id"]]["business_unit_id"] for row in recent
             if row["order_line_id"] in lines}
    months = account.get("monthly_commercial_history", ())
    revision = next((row for row in account.get("quote_revisions", ())
                     if row["quote_revision_id"] == opportunity.get("quote_revision_id")), None)
    quote = next((row for row in account.get("quotes", ()) if revision and row["quote_id"] == revision["quote_id"]), None)
    complete = len(months) == 12 and all("revenue_minor" in row and "snapshot_id" in row for row in months)
    if complete and all(row["order_line_id"] in lines for row in recent) and units:
        value = "EXISTING_MULTI_BU_ACTIVE" if len(units) >= 2 else "EXISTING_ONE_BU_ACTIVE"
        evidence = tuple(row["revenue_event_id"] for row in recent)
    elif complete and not recent and quote and all(row["revenue_minor"] == 0 for row in months):
        value = "QUOTE_OR_WARM_NO_SALES"
        evidence = (quote["quote_id"], *(row["snapshot_id"] for row in months))
    elif not months and account.get("relationship_state") in {"PUBLIC_MARKET", "NO_RELATIONSHIP_EVIDENCE"}:
        value = "COLD_PROSPECT"
        evidence = (opportunity["opportunity_id"],)
    else:
        value, evidence = None, ()
    return deterministic_bin(
        opportunity_id=opportunity["opportunity_id"], path=PATH, bin_value=value,
        evidence_ids=evidence, missing_fields=() if value else ("commercial_history_or_scoped_quote",),
        as_of=as_of, rule_version=SAMPLE_CLASSIFIER_RULE_VERSION,
    )
