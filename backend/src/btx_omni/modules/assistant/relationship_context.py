"""Resolve UI path references again; browser-supplied factors are never accepted."""
from datetime import date
from decimal import Decimal

from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.relationships.presentation import (
    seller_route_evidence_label,
    seller_route_predicate_label,
)
from btx_omni.modules.relationships.routes import RouteQuery
from btx_omni.modules.relationships.service import RelationshipIntelligenceService


def selected_relationship_context(environment, selection: dict, *, account_id: str | None) -> dict:
    source = selection["source_account_id"]
    if account_id and account_id != source:
        raise ValueError("Selected route does not belong to the explicit account scope")
    if source not in environment.commercial_ledgers:
        raise ValueError("Selected route source is unavailable")
    as_of = selection["as_of"]
    query = RouteQuery("SAMPLE", f"SAMPLE:account:{source}", frozenset(selection["target_ids"]), selection["mode"],
                       date.fromisoformat(as_of) if isinstance(as_of, str) else as_of,
                       frozenset(a.id for a in environment.accounts), selection.get("source_component_id"),
                       selection.get("target_component_id"), selection["depth"])
    result = RelationshipIntelligenceService(environment).ranked_routes(query, selected_path_id=selection["path_id"])
    if result["eligible_graph_revision"] != selection["graph_revision"]:
        raise ValueError("Selected graph revision is stale; refresh the route before explaining it")
    route = next(r for r in result["evaluated_routes"] if r["path_id"] == selection["path_id"])
    # Bounded source records, with explicit omitted count; consumers may retrieve deeper evidence.
    records = []
    account_ids = {step["account_id"] for step in route["steps"] if step.get("account_id")}
    for eid in route["evidence_ids"]:
        if len(records) >= 8:
            break
        for aid in sorted(account_ids):
            record = resolve_commercial_evidence(environment.commercial_ledgers.get(aid, {}), eid)
            if record:
                records.append({"account_id": aid, **record})
                break
    connection = " → ".join(step["label"] for step in route["steps"])
    components = "; ".join(c['label'] for c in route["component_context"])
    reasons = " ".join(item["reason"] for item in route["factor_reasons"])
    constraints = " ".join(item["reason"] for item in route["constraints"])
    weakest = min(route["factor_reasons"], key=lambda item: (item["B"], item["E"], item["F"])) if route["factor_reasons"] else None
    route_state = seller_route_evidence_label(weakest["truth_class"] if weakest else "NEEDS_VALIDATION")
    content = f"Selected connection: {connection}. Route status: {route_state}. Component scope: {components or 'recorded role scope'}. Why useful: {reasons} Weakest or unresolved connection: {weakest['reason'] if weakest else constraints or 'Current qualification and spare capacity are not established by this route.'} Limiting fact: {constraints or 'Current qualification and spare capacity are not established by this route.'} Next validation action: {route['next_action']}"
    financial_facts = []
    account_names = {item.id: item.legal_name for item in environment.accounts}
    for item in records:
        record = item["record"]
        fields = {key: value for key, value in record.items() if key.endswith(("_minor", "_date")) or key in {"quantity", "currency", "buyer_accepted"}}
        if fields:
            currency = environment.commercial_ledgers[item["account_id"]]["currency"]
            from btx_omni.modules.commercial.money import model_money_projection
            financial_facts.append(f"{item['record_id']} ({account_names.get(item['account_id'], 'selected account')}, {currency}): {model_money_projection(fields, currency=currency)}")
    expanded_content = "Linked records (money display is already formatted by canonical server code): " + "; ".join(financial_facts)
    for aid in sorted(account_ids):
        ledger = environment.commercial_ledgers.get(aid)
        if ledger:
            revenue = Decimal(ledger["ttm_summary"]["revenue_minor"]) / 100
            content += f"\n{account_names.get(aid, 'Selected account')}: {ledger['currency']} {revenue:,.2f} recognized revenue across {len(ledger['monthly_commercial_history'])} recorded months through {ledger['as_of']} (account-wide, not component-only)."
            from btx_omni.modules.commercial.money import model_money_projection
            expanded_content += f"\nAccount-wide trailing-12-month summary for {account_names.get(aid, 'the selected account')}, through {ledger['as_of']}: {model_money_projection(ledger['ttm_summary'], currency=ledger['currency'])}."
    source_links = tuple(
        {"label": f"Supporting source for {seller_route_predicate_label(assertion['predicate'])}", "url": assertion["source_url"]}
        for assertion in route.get("assertions", ())
        if assertion.get("source_url")
    )
    return {"route": route, "graph_revision": result["eligible_graph_revision"], "search_complete": result["search_complete"],
            "rubric_version": result["rubric_version"], "commercial_as_of": result["commercial_as_of"],
            "content": content, "expanded_content": expanded_content, "evidence_records": records,
            "evidence_records_omitted": max(0, len(route["evidence_ids"]) - len(records)),
            "source_links": source_links,
            "authority": "Canonical route factors and constraints; model language cannot modify this structured result."}
