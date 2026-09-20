"""Tenant-scoped projection of imported professional-network assertions."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime

from btx_omni.modules.relationships.routes import (
    CanonicalRouteGraph,
    RouteEdge,
    RouteNode,
)
from btx_omni.persistence.commercial_import import digest
from btx_omni.providers.sample.environment import SampleEnvironment


def _day(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def project_network_graph(sample: SampleEnvironment, rows: tuple[dict[str, object], ...], *, tenant_id: str) -> tuple[CanonicalRouteGraph, dict]:
    """Project only rows already authorized by NetworkImportRepository."""
    scope = f"TENANT:{tenant_id}"
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get("account_id"):
            grouped[str(row["account_id"])].append(row)
    nodes: dict[str, RouteNode] = {}
    edges: list[RouteEdge] = []
    account_names = {account.id: account.legal_name for account in sample.accounts}
    buyer_roles = {
        account_id: " ".join(str(role.get("verified_function") or role.get("label") or "").casefold()
                             for role in ledger.get("role_targets", ()))
        for account_id, ledger in sample.commercial_ledgers.items()
    }
    for account_id, name in account_names.items():
        contacts = grouped.get(account_id, [])
        sources = tuple(sorted({str(item["owner_display_name"]) for item in contacts}))
        node = RouteNode(scope, "account", account_id, name, account_id,
                         contact_count=len(contacts), senior_contact_count=sum(item["seniority_tier"] in {"executive", "director"} for item in contacts),
                         source_people=sources, unvalidated=bool(contacts))
        nodes[node.id] = node
    seniority_order = {"executive": 0, "director": 1, "manager": 2, "individual": 3, "unclassified": 4}
    projected_rows = sorted(rows, key=lambda item: (
        seniority_order.get(str(item["seniority_tier"]), 5), str(item["role_family"]), str(item["person_id"])
    ))[:250]
    owners: dict[str, RouteNode] = {}
    for row in projected_rows:
        account_id = row.get("account_id")
        if not account_id or str(account_id) not in account_names:
            continue
        exported = _day(row.get("as_of") or row.get("exported_at"))
        owner_id = str(row["internal_person_id"])
        owner = owners.get(owner_id)
        if owner is None:
            owner = RouteNode(scope, "internal_person", owner_id, str(row["owner_display_name"]), unvalidated=True)
            owners[owner_id] = owner
            nodes[owner.id] = owner
        person_id = str(row["person_id"])
        provenance = f"LinkedIn connection from {row['owner_display_name']}'s export dated {exported.isoformat() if exported else 'date unavailable'}, not validated"
        external = RouteNode(scope, "external_contact", person_id, str(row["display_name"]), str(account_id),
                             unvalidated=True, role_family=str(row["role_family"]), seniority_tier=str(row["seniority_tier"]),
                             profile_url=str(row["profile_url"]) if row.get("profile_url") else None,
                             raw_title=str(row["raw_title"]) if row.get("raw_title") else None,
                             provenance_label=provenance, exported_on=exported,
                             resolution_method=str(row["resolution_method"]))
        nodes[external.id] = external
        evidence_id = f"network:{row['batch_id']}:{person_id}"
        family = str(row["role_family"])
        family_terms = {
            "procurement": ("procurement", "sourcing"), "supply_chain": ("supply", "planning"),
            "supplier_management": ("supplier", "quality"), "engineering": ("engineering",),
            "manufacturing": ("manufacturing", "production"), "operations": ("operations", "delivery"),
        }.get(family, ())
        role_match = any(term in buyer_roles.get(str(account_id), "") for term in family_terms)
        relevance = 3 if role_match and row["seniority_tier"] in {"executive", "director"} else 2 if role_match else 1
        edges.append(RouteEdge(f"works-at:{row['batch_id']}:{person_id}", external.id, f"{scope}:account:{account_id}", "WORKS_AT",
                               (evidence_id,), (evidence_id,), ("network_import",), "ANALYST_INFERENCE", exported,
                               account_id=str(account_id), inverse_modes=("contact_candidates", "documented_access"), relevance_score=relevance))
        edges.append(RouteEdge(f"knows:{row['batch_id']}:{owner_id}:{person_id}", owner.id, external.id, "KNOWS",
                               (evidence_id,), (evidence_id,), ("network_import",), "ANALYST_INFERENCE", exported,
                               account_id=str(account_id), inverse_modes=("documented_access",), relevance_score=relevance))
    revision = digest({"projection": "BTX_NETWORK_GRAPH_1", "tenant": tenant_id,
                       "batches": sorted(Counter(str(row["batch_id"]) for row in rows).items())})
    return CanonicalRouteGraph(tuple(nodes.values()), tuple(edges), revision), {
        "constraints": {}, "temporal_limits": {}, "record_projection": {"unresolved_references": []},
        "scope": "Tenant-scoped imported network rows", "account_names": account_names,
        "network_contact_count": len(rows), "network_projected_contact_count": len(projected_rows),
    }


def prompt_safe_network_context(rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    """Allowlisted aggregate context; imported PII must never cross an LLM boundary."""
    return {
        "contact_count": len(rows),
        "role_family_counts": dict(sorted(Counter(str(row["role_family"]) for row in rows).items())),
        "seniority_tier_counts": dict(sorted(Counter(str(row["seniority_tier"]) for row in rows).items())),
        "provenance": "LinkedIn export, not validated",
    }
