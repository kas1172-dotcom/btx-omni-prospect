"""Actor-bound read adapters. No business mutation capability is imported here."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from btx_omni.domain.work import PrincipalRole
from btx_omni.modules.accounts.customer_360 import organization_360_projection
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.assistant.chat_web import PublicTopic, public_query, search
from btx_omni.modules.assistant.commercial_tools import CommercialToolSession
from btx_omni.modules.commercial.money import model_money_projection
from btx_omni.modules.commercial.read import CommercialReadService
from btx_omni.modules.relationships.service import RelationshipIntelligenceService


class Empty(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Find(Empty):
    name: str = Field(min_length=1, max_length=160)


class AccountInput(Empty):
    account_id: str = Field(min_length=1, max_length=64)


class OptionalAccount(Empty):
    account_id: str | None = Field(default=None, max_length=64)


class History(AccountInput):
    quote_id: str | None = Field(default=None, max_length=220)


class Compare(Empty):
    account_ids: list[str] = Field(min_length=2, max_length=2)


class Search(OptionalAccount):
    topic: PublicTopic

    model_config = ConfigDict(extra="forbid", strict=False)


class ReadResult(Empty):
    status: Literal["ok", "too_large", "timeout"]
    as_of: str
    source_ids: list[str] = Field(max_length=40)
    data_mode: str
    data: dict


INPUTS = {
    "web_search": (Search, "Search public sources using only a recorded public company name and an approved topic. No free-form queries or internal values."),
    "find_organization": (Find, "Resolve a recorded organization name; never infer identity from industry words."),
    "get_customer_360": (AccountInput, "Organization identity and relationship context."),
    "get_commercial_history": (History, "Sample orders, quote rows and revisions, shipments, backlog and periods."),
    "get_intelligence_events": (OptionalAccount, "Stored visible public developments and sources."),
    "get_assessments": (AccountInput, "Separate deterministic score families, factors, Data Coverage, eligibility and rule versions."),
    "get_relationship_routes": (AccountInput, "Documented relationships, constraints and contact candidates; never assumed access."),
    "get_nearby_sites": (AccountInput, "Verified sites and straight-line distances, never route times."),
    "get_actions": (OptionalAccount, "Actions visible to this user; cannot create or change work."),
    "get_today_priorities": (OptionalAccount, "Deterministic alerts and current visible work."),
    "get_federal_opportunities": (OptionalAccount, "Current stored federal opportunities, if available."),
    "compare_organizations": (Compare, "Two independently resolved organizations; never calculate a combined score."),
    "get_screen_context": (Empty, "Current screen and validated selection; screen text is not evidence."),
}


def source_ids(value):
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"source_record_id", "evidence_id", "id", "quote_id", "order_id"} and isinstance(item, str):
                result.add(item)
            elif key in {"evidence_ids", "source_ids"} and isinstance(item, (list, tuple)):
                result.update(x for x in item if isinstance(x, str))
            result.update(source_ids(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            result.update(source_ids(item))
    return result


class ChatTools:
    """The API supplies its authorized catalog and current-principal work projection.

    Core app catalogs are workspace-wide today. allowed_account_ids is server-owned,
    never model/browser supplied. Private imported networks are deliberately excluded.
    """

    def __init__(self, sample, principal, *, observed_at, context=None, events=(),
                 work=(), allowed_account_ids=None, federal_reader=None, provider=None,
                 web_enabled=True, general_enabled=True):
        if not principal or not principal.user_id:
            raise PermissionError("An authenticated user is required.")
        self.sample, self.principal, self.observed_at = sample, principal, observed_at
        self.allowed = frozenset(a.id for a in sample.accounts) if allowed_account_ids is None else frozenset(allowed_account_ids)
        self.accounts = {a.id: a for a in sample.accounts if a.id in self.allowed}
        self.events = tuple(e for e in events if e.get("account_id") in self.allowed)
        self.work = tuple(w for w in work if w.account_id in self.allowed and (
            principal.role is PrincipalRole.MANAGER or w.owner_id in {None, principal.user_id}
            or w.created_by == principal.user_id))
        self.context = context or {}
        self.federal_reader = federal_reader
        self.named_scope: frozenset[str] = frozenset()
        self.provider, self.web_enabled, self.general_enabled = provider, web_enabled, general_enabled
        self.outbound_queries = []

    @property
    def declarations(self):
        return [{"name": name, "description": desc, "input_schema": schema.model_json_schema(),
                 "output_schema": ReadResult.model_json_schema()}
                for name, (schema, desc) in INPUTS.items()]

    def names(self, account):
        return [account.legal_name, *(a.value for a in account.public_identity.aliases)] if account.public_identity else [account.legal_name]

    def named(self, question):
        matches = [(len(name), a.id) for a in self.accounts.values() for name in self.names(a)
                   if len(name) >= 3 and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", question, re.IGNORECASE)]
        return tuple(dict.fromkeys(aid for _, aid in sorted(matches, reverse=True)))

    def find(self, name):
        available = [a for a in self.accounts.values() if not self.named_scope or a.id in self.named_scope]
        exact = [a for a in available if name.strip().casefold() in {n.casefold() for n in self.names(a)}]
        if len(exact) == 1:
            return {"status": "matched", "confidence": "EXACT_RECORDED_NAME", "candidates": [{"id": exact[0].id, "name": exact[0].legal_name}]}
        similar = sorted(((max(SequenceMatcher(None, name.casefold(), n.casefold()).ratio() for n in self.names(a)), a.id)
                          for a in available), reverse=True)
        candidates = [{"id": aid, "name": self.accounts[aid].legal_name} for score, aid in similar[:3] if score >= .68]
        return {"status": "candidates" if len(exact) > 1 else "not_found", "confidence": "UNRESOLVED", "candidates": candidates}

    def account(self, account_id):
        if account_id not in self.accounts or (self.named_scope and account_id not in self.named_scope):
            raise PermissionError("That organization is outside this question's authorized scope.")
        return self.accounts[account_id]

    def execute(self, name, arguments):
        if name not in INPUTS:
            raise ValueError("Unknown read tool.")
        params = INPUTS[name][0].model_validate(arguments).model_dump()
        aid = params.get("account_id")
        if aid:
            self.account(aid)
        elif name not in {"find_organization", "get_screen_context", "compare_organizations"} and len(self.named_scope) == 1:
            aid = next(iter(self.named_scope))
        data = self._read(name, aid, params)
        encoded = jsonable_encoder(data)
        result = {"status": "ok", "as_of": self.observed_at.date().isoformat(),
                  "source_ids": sorted(source_ids(encoded))[:40], "data_mode": "PUBLIC_WEB" if name == "web_search" else "SAMPLE", "data": encoded}
        if name == 'web_search':
            result['as_of'] = datetime.now(UTC).date().isoformat()
        if len(json.dumps(result)) > 24000:
            return {**result, "status": "too_large", "data": {"message": "This result is too large. Ask about a specific record."}}
        return ReadResult.model_validate(result).model_dump()

    def _read(self, name, aid, params):
        if name == "web_search":
            if not self.web_enabled or not getattr(self.provider, "configured", False):
                return {"status": "unavailable", "message": "Public search isn't available right now."}
            company = self.account(aid).legal_name if aid else None
            query = public_query(params["topic"], company)
            self.outbound_queries.append(query)
            return search(self.provider, query, company, datetime.now(UTC))
        if name == "find_organization":
            return self.find(params["name"])
        if name == "get_screen_context":
            return {"surface": self.context.get("surface"), "selected_account_id": self.context.get("selected_account_id") if self.context.get("selected_account_id") in self.accounts else None,
                    "visible_record_ids": [x for x in self.context.get("visible_record_ids", [])[:50] if x in self.accounts or any(e.get('id') == x for e in self.events) or any(w.id == x for w in self.work)],
                    "active_filters": self.context.get("active_filters", {})}
        if name == "compare_organizations":
            ids = params["account_ids"]
            if len(set(ids)) != 2:
                raise ValueError("Select two different organizations.")
            return {"organizations": [self._read("get_customer_360", self.account(x).id, {}) for x in ids]}
        if name == "get_customer_360":
            a = self.account(aid)
            commercial = CommercialReadService(self.sample).account_snapshot(aid)
            return {"id": aid, "name": a.legal_name, "industries": a.industries, "domain": a.domain,
                    "source_record_id": getattr(a.provenance, "source_record_id", None),
                    "source_url": getattr(a.provenance, "source_url", None),
                    "organization": organization_360_projection(account=a, commercial=commercial, signals=[e for e in self.events if e.get("account_id") == aid])}
        if name == "get_commercial_history":
            snapshot = CommercialReadService(self.sample).account_snapshot(aid)
            def rows(values, fields):
                return [{key: row.get(key) for key in fields} for row in jsonable_encoder(values[:10])]
            result = {"account_id": aid, "name": self.account(aid).legal_name, "quote_count": len(snapshot.quotes),
                      "order_count": len(snapshot.orders),
                      "quotes": rows(snapshot.quotes, ("id", "status", "quoted_at", "value", "currency")),
                      "orders": rows(snapshot.orders, ("id", "quote_id", "status", "quantity", "amount", "promised_date", "actual_ship_date")),
                      "omitted_quotes": max(0, len(snapshot.quotes) - 10), "omitted_orders": max(0, len(snapshot.orders) - 10)}
            if aid in self.sample.commercial_ledgers:
                session = CommercialToolSession(self.sample, aid, work_items=self.work)
                history = session.read("read_history", {})
                history.pop("case_briefing", None)  # Free-text briefing repeats the underlying records.
                history.pop("monthly_history", None)
                fulfillment = session.read("read_fulfillment", {})
                recorded_lines = {line['order_line_id']: line for line in self.sample.commercial_ledgers[aid]['order_lines']}
                for line in fulfillment['lines']:
                    recorded = recorded_lines[line['order_line_id']]
                    # Same integer quantity x recorded unit price arithmetic as customer_health.
                    # Presentation-only value; never a model calculation or scoring input.
                    line['remaining_value_minor'] = line['remaining_quantity'] * recorded['unit_price_minor']
                result.update(history=history, fulfillment=fulfillment)
                if params.get("quote_id"):
                    result["quote_comparison"] = session.read("compare_quote_revisions", {"quote_id": params["quote_id"]})
                return model_money_projection(jsonable_encoder(result), currency=self.sample.commercial_ledgers[aid]["currency"])
            return result
        if name == "get_assessments":
            if aid not in self.sample.commercial_ledgers:
                return {"status": "unavailable", "message": "Detailed assessment inputs aren't loaded for this organization. Open its profile to inspect available public fit information."}
            decisions = CommercialToolSession(self.sample, aid, work_items=self.work).read("read_decisions", {})
            # Action execution detail is available separately from get_actions.
            decisions.pop("action_priorities", None)
            return decisions
        if name == "get_relationship_routes":
            result = RelationshipIntelligenceService(self.sample).account_relationships(aid, depth=2, max_paths=6)
            # Legacy graph projection has no private imported network records.
            if self.allowed != frozenset(a.id for a in self.sample.accounts):
                return {"status": "unavailable", "message": "Relationship context requires an authorized graph projection."}
            contacts = CommercialToolSession(self.sample, aid).read('read_contact_candidates', {}) if aid in self.sample.commercial_ledgers else {'contacts': [], 'status': 'unavailable'}
            return {"relationships": result, 'contact_candidates': contacts, "limitation": "A hypothetical route is not established access. Leadership contacts do not imply buying authority or a confirmed meeting."}
        if name == "get_nearby_sites":
            from btx_omni.api.map import haversine_miles
            origins = [f for f in self.sample.public_facilities if f.account_id == aid]
            if not origins:
                return {"status": "unavailable", "message": "No verified origin site is recorded."}
            origin = origins[0]
            sites = [{"id": f.id, "name": f.name, "account_id": f.account_id, "source_url": f.source_url,
                      "distance_miles": haversine_miles(origin.latitude, origin.longitude, f.latitude, f.longitude)}
                     for f in self.sample.public_facilities if f.account_id in self.allowed and f.id != origin.id]
            return {"origin": origin.name, "sites": sorted(sites, key=lambda x: x["distance_miles"])[:10],
                    "limitation": "Straight-line miles from the first recorded site, not route time or a confirmed meeting."}
        if name == "get_intelligence_events":
            return {"events": [e for e in self.events if not aid or e.get("account_id") == aid][:10]}
        if name == "get_actions":
            return {"actions": [w for w in self.work if not aid or w.account_id == aid][:10]}
        if name == "get_today_priorities":
            alerts = CommercialAlertEngine().evaluate(self.sample.commercial_contexts, self.sample.quotes,
                                                     observed_at=self.observed_at, orders=self.sample.orders)
            return {"alerts": [a for a in alerts if a.account_id in self.allowed and (not aid or a.account_id == aid)][:5],
                    "actions": [w for w in self.work if not aid or w.account_id == aid][:5]}
        if name == "get_federal_opportunities":
            return self.federal_reader(aid) if self.federal_reader else {"status": "unavailable", "message": "Federal opportunity data isn't available in this context."}
        raise ValueError("Unsupported read.")
