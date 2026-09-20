"""Bounded model-selected reads reuse canonical owners, never model-owned decisions."""
import json
import re
from hashlib import sha256
from time import monotonic

from btx_omni.ai.contracts import CanonicalToolSelectionRequest, LanguageProviderError
from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.commercial.lifecycle import fulfillment_state
from btx_omni.modules.commercial.read import CommercialReadService
from btx_omni.modules.scoring.commercial_decisions import customer_decisions

DEFINITIONS = (
    {"name": "read_history", "description": "TTM, all twelve monthly histories and available quote IDs. No arguments.", "arguments": []},
    {"name": "compare_quote_revisions", "description": "Compare a quote's revisions, integer amounts, changes and individual lines. Required quote_id from read_history.", "arguments": ["quote_id"]},
    {"name": "read_fulfillment", "description": "Current order lines, partial shipments, remaining quantities, acceptance and actual delivery constraints. No arguments.", "arguments": []},
    {"name": "read_decisions", "description": "Canonical separate decision factors, coverage, qualification gaps and local work state. No arguments.", "arguments": []},
    {"name": "read_evidence", "description": "Look up an exact record ID from the user's request, selected context or prior reads, within this account only. Reports a missing record without substituting another. Public-source metadata is not current full-article research.", "arguments": ["record_id"]},
    {"name": "read_contact_candidates", "description": "Researched professional candidates plus distinct role targets and role-only interactions; never infer personal introductions. No arguments.", "arguments": []},
    {"name": "read_selected_relationship", "description": "Already revalidated selected relationship, ordered edges, factors and limiting constraints. No arguments.", "arguments": []},
    {"name": "read_selected_market", "description": "Revalidated selected public market series, numeric trend, current vintage, limitations and exposed accounts. Never customer orders or scoring inputs. No arguments.", "arguments": []},
)


def _mentioned_ids(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_id") and isinstance(child, str):
                found.add(child)
            if key.endswith("_ids") and isinstance(child, (list, tuple)):
                found.update(item for item in child if isinstance(item, str))
            found.update(_mentioned_ids(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_mentioned_ids(child))
    return found


class CommercialToolSession:
    """Scope is server-resolved once; the model cannot select another account or owner."""
    def __init__(self, sample, account_id, *, work_items=(), selected_relationship=None, selected_market=None):
        self.sample, self.account_id = sample, account_id
        self.ledger = sample.commercial_ledgers[account_id]
        self.work = tuple(work_items)
        self.relationship = selected_relationship
        self.market = selected_market

    def read(self, name, arguments):
        definition = next((d for d in DEFINITIONS if d["name"] == name), None)
        if definition is None or not isinstance(arguments, dict) or set(arguments) != set(definition["arguments"]):
            raise ValueError("Unsupported canonical read or arguments.")
        if any(not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:._-]{0,219}', value) is None for value in arguments.values()):
            raise ValueError("Invalid bounded record identifier.")
        ledger = self.ledger
        if name == "read_history":
            return CommercialReadService(self.sample).account_snapshot(self.account_id).ledger_summary | {
                "quotes": [{k: q.get(k) for k in ("quote_id", "status", "current_revision_id", "accepted_revision_id")} for q in ledger["quotes"]],
                "case_briefing": ledger.get("commercial_case", {}),
            }
        if name == "compare_quote_revisions":
            return CommercialReadService(self.sample).quote_comparison(self.account_id, arguments["quote_id"])
        if name == "read_fulfillment":
            state = fulfillment_state(ledger, canonical_account_id=self.account_id, revision=self.sample.commercial_revision)
            open_lines = [line for line in state["lines"] if line["remaining_quantity"] or line["shipped_unaccepted_quantity"] or line["constraints"]]
            retained = {line["order_line_id"] for line in open_lines}
            recent_closed = sorted((line for line in state["lines"] if line["order_line_id"] not in retained),
                                   key=lambda line: (line["committed_date"] or "", line["order_line_id"]), reverse=True)[:3]
            current_totals = {key: state['recorded_history_totals'][key] for key in (
                'remaining_quantity', 'shipped_unaccepted_quantity', 'shipped_unaccepted_value_minor')}
            return {**state, "lines": [*open_lines, *recent_closed], "closed_lines_omitted": len(state["lines"]) - len(open_lines) - len(recent_closed),
                    'recorded_history_totals': current_totals,
                    'omitted_totals': 'Historical ordered/shipped/accepted quantities and opening-history revenue are omitted from this current-fulfillment read. They are not TTM totals; inspect linked historical records separately.',
                    "ttm_summary": ledger["ttm_summary"], "ttm_months": [m["period"] for m in ledger["monthly_commercial_history"]]}
        if name == "read_decisions":
            account = next(a for a in self.sample.accounts if a.id == self.account_id)
            result = customer_decisions(ledger, account_id=self.account_id, revision=self.sample.commercial_revision,
                                        facility_ids=frozenset(f.id for f in self.sample.btx_facilities),
                                        current_customer=account.relationship.value in {"CURRENT_CUSTOMER", "FORMER_CUSTOMER"}, work_items=self.work)
            # Bound evidence lists, not the decision's required fields or calculated values.
            def bounded(value):
                if isinstance(value, dict):
                    if "decision_id" in value:
                        return {k: bounded(value[k]) for k in ("decision_id", "family", "subject_id", "score", "score_range", "configuration_version", "rule_version", "weighted_score", "weighted_band", "band", "what_would_change_result", "status", "priority_rank", "priority_class", "eligibility_reasons", "blocking_constraints", "factors", "data_coverage") if k in value}
                    if "points" in value and "required_fields" in value:
                        return {"key": value["key"], "points": value["points"], "weight": value["weight"],
                                "contribution": value.get('contribution'), "evidence_state": value.get('evidence_state'),
                                "raw_value": value.get('raw_value'), "period": value.get('period'),
                                "reason": value["reason"], "truth_class": value["truth_class"],
                                "missing_fields": sorted(set(value["required_fields"]) - set(value["observed_fields"])),
                                "evidence_ids": value["evidence_ids"][:5], "evidence_ids_omitted": max(0, len(value["evidence_ids"]) - 5)}
                    return {k: (v[:5] if k == "evidence_ids" and isinstance(v, (tuple, list)) else bounded(v)) for k, v in value.items()} | ({"evidence_ids_omitted": max(0, len(value["evidence_ids"]) - 5)} if "evidence_ids" in value else {})
                if isinstance(value, (tuple, list)):
                    return [bounded(v) for v in value]
                return value
            return {"as_of": ledger["as_of"], "revision": self.sample.commercial_revision,
                    "configuration_version": result["customer_health"]["configuration_version"], **bounded(result)}
        if name == "read_evidence":
            evidence = resolve_commercial_evidence(ledger, arguments["record_id"])
            if evidence is None:
                return {'kind': 'record_lookup', 'status': 'NOT_FOUND_IN_ACCOUNT', 'record_id': arguments['record_id'],
                        'account_id': self.account_id, 'revision': self.sample.commercial_revision,
                        'as_of': ledger['as_of'], 'record': None,
                        'limitation': 'No matching record is available in this account scope. This does not establish global absence or reveal another account. Do not invent amounts, dates, substitute records or a payment.'}
            return evidence
        if name == "read_contact_candidates":
            return {"contacts": ledger["contacts"], "role_targets": ledger["role_targets"],
                    "recent_interactions": sorted(ledger["interactions"], key=lambda r: r["date"])[-3:],
                    "limitation": "Published roles are contact candidates, not personal access. Role-target interaction events cannot be assigned to researched people."}
        if name == "read_selected_relationship":
            return self.relationship or {"status": "NO_SELECTED_ROUTE", "next_action": "Select a route in the relationship workspace."}
        if name == 'read_selected_market':
            return self.market or {'status': 'NO_SELECTED_MARKET', 'next_action': 'Select a verified market series in Intelligence.'}
        raise ValueError("Unavailable canonical read.")

    def run(self, provider, question: str, *, max_calls=4, deadline_seconds=20, canceled=lambda: False):
        if not 1 <= max_calls <= 4 or not 0 <= deadline_seconds <= 20:
            raise ValueError("Canonical read budgets exceed the POC configuration.")
        start = monotonic()
        reads, steps, seen = [], [], set()
        stop = "TOOL_BUDGET"
        rejected = None
        definitions = tuple(d for d in DEFINITIONS
                            if (d['name'] != 'read_selected_relationship' or self.relationship)
                            and (d['name'] != 'read_selected_market' or self.market))
        for index in range(max_calls):
            if canceled() or monotonic() - start >= deadline_seconds:
                stop = "CANCELED" if canceled() else "DEADLINE"
                break
            try:
                selection = provider.choose_canonical_read(CanonicalToolSelectionRequest(
                    question, self.account_id, definitions, tuple(reads), max_calls - index))
                if selection == {"done": True}:
                    stop = "MODEL_DONE"
                    break
                if not isinstance(selection, dict) or set(selection) != {"tool", "arguments"}:
                    raise ValueError("Invalid canonical read selection.")
                if selection['tool'] not in {d['name'] for d in definitions}:
                    raise ValueError('Tool is not available in the selected context.')
                if canceled() or monotonic() - start >= deadline_seconds:
                    stop = "CANCELED" if canceled() else "DEADLINE"
                    break
                key = json.dumps(selection, sort_keys=True)
                if key in seen:
                    stop = "REPEATED_READ"
                    break
                seen.add(key)
                value = self.read(selection["tool"], selection["arguments"])
                encoded = json.dumps(value, default=str, sort_keys=True)
                if len(encoded) > 24000 or sum(len(json.dumps(r, default=str)) for r in reads) + len(encoded) > 48000:
                    stop = "EVIDENCE_BUDGET"
                    break
                reads.append({"tool": selection["tool"], "arguments": selection["arguments"], "result": value})
                evidence_ids = sorted(eid for eid in _mentioned_ids(value) if resolve_commercial_evidence(self.ledger, eid))
                steps.append({"step": index + 1, "tool": selection["tool"], "arguments": selection["arguments"],
                              "result_checksum": sha256(encoded.encode()).hexdigest(), "result_characters": len(encoded),
                              "evidence_ids": evidence_ids, "status": "READ_COMPLETED"})
            except LanguageProviderError as error:
                stop = "PROVIDER_" + error.status.value
                break
            except (ValueError, KeyError, TypeError, RuntimeError, TimeoutError) as error:
                stop = "READ_SELECTION_FAILED"
                proposed = locals().get("selection")
                rejected = {"error_class": type(error).__name__, "stage": "CANONICAL_SELECTION_OR_READ",
                            "tool": proposed.get("tool") if isinstance(proposed, dict) and proposed.get("tool") in {d["name"] for d in DEFINITIONS} else "UNRECOGNIZED",
                            "argument_keys": sorted(proposed.get("arguments", {}).keys()) if isinstance(proposed, dict) and isinstance(proposed.get("arguments"), dict) else [],
                            "controlled_error": str(error)[:180] if isinstance(error, KeyError) else None}
                break
        return {"account_id": self.account_id, "revision": self.sample.commercial_revision,
                "steps": steps, "reads": reads, "stop_reason": stop,
                "rejected_selection": rejected,
                "elapsed_ms": round((monotonic() - start) * 1000, 2), "max_calls": max_calls,
                "configuration_version": "OMNI_CANONICAL_READS_POC_3",
                "deadline_policy": f"No new step starts after {deadline_seconds}s; an in-flight provider call is bounded by its configured transport timeout.",
                "model_requested_stop": stop == "MODEL_DONE"}
