"""Authenticated relationship queries; one configured SAMPLE namespace."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from btx_omni.api.accounts import get_runtime
from btx_omni.api.intelligence_projection import intelligence_signals
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.session import principal
from btx_omni.domain.work import Principal
from btx_omni.modules.relationships.routes import RouteQuery
from btx_omni.modules.relationships.service import RelationshipIntelligenceService
from btx_omni.persistence.commercial_import import BU_CROSSWALK

router = APIRouter(prefix="/relationships", tags=["relationships"])


class RelationshipQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_account_id: str = Field(min_length=1, max_length=64)
    target_account_id: str | None = Field(default=None, max_length=64)
    mode: Literal[
        "commercial_fit",
        "cross_account_experience",
        "contact_candidates",
        "documented_access",
    ] = "cross_account_experience"
    as_of: date | None = None
    depth: int = Field(default=4, ge=1, le=6)
    source_component_id: str | None = Field(default=None, max_length=220)
    target_component_id: str | None = Field(default=None, max_length=220)
    target_facility_id: str | None = Field(default=None, max_length=220)
    selected_path_id: str | None = Field(default=None, max_length=100)
    node_budget: int = Field(default=24, ge=7, le=80)
    edge_budget: int = Field(default=40, ge=6, le=160)
    expanded_node_ids: tuple[
        Annotated[str, Field(min_length=1, max_length=220)], ...
    ] = Field(default=(), max_length=8)
    context_page: int = Field(default=0, ge=0, le=200)
    expected_graph_revision: str | None = Field(default=None, max_length=100)
    include_record_context: bool = False


@router.post("/query")
def relationship_query(
    body: RelationshipQuery,
    response: Response,
    actor: Principal = Depends(principal),
    runtime: PocRuntime = Depends(get_runtime),
) -> dict:
    sample = runtime.environment()
    accounts = {a.id: a for a in sample.accounts}
    if body.source_account_id not in accounts:
        raise HTTPException(404, "Canonical source account not found")
    if body.target_account_id and body.target_account_id not in accounts:
        raise HTTPException(404, "Canonical target account not found")
    if not sample.commercial_ledgers:
        raise HTTPException(
            503, "Persisted relationship evidence has not been imported"
        )
    source = sample.commercial_ledgers.get(body.source_account_id)
    if source is None:
        raise HTTPException(
            404, "No scoped commercial graph evidence for this account yet"
        )
    if body.source_component_id and body.source_component_id not in {
        c["component_id"] for c in source["components"]
    }:
        raise HTTPException(
            404, "Component is not owned by the selected source account"
        )
    if body.target_component_id and (
        not body.target_account_id or body.mode != "cross_account_experience"
    ):
        raise HTTPException(
            422,
            "A compared component requires an explicit compared account and experience objective",
        )
    if (
        body.target_component_id
        and body.target_account_id
        and body.target_component_id
        not in {
            c["component_id"]
            for c in sample.commercial_ledgers.get(body.target_account_id, {}).get(
                "components", []
            )
        }
    ):
        raise HTTPException(
            404, "Component is not owned by the selected target account"
        )
    if (
        body.target_facility_id
        and body.mode != "commercial_fit"
        or body.target_account_id
        and body.mode != "cross_account_experience"
    ):
        raise HTTPException(422, "Target type does not match the selected objective")
    from btx_omni.modules.relationships.canonical_projection import FACILITY_CROSSWALK

    if body.mode == "cross_account_experience":
        units = {BU_CROSSWALK[c["business_unit_id"]] for c in source["components"]}
        target_ids = {
            f"SAMPLE:account:{aid}"
            for aid, a in sample.commercial_ledgers.items()
            if aid != body.source_account_id
            and (
                aid == body.target_account_id
                if body.target_account_id
                else units
                & {BU_CROSSWALK[c["business_unit_id"]] for c in a["components"]}
            )
        }
    elif body.mode == "commercial_fit":
        target_ids = {
            f"SAMPLE:btx_facility:{FACILITY_CROSSWALK.get(c['btx_facility_id'], c['btx_facility_id'])}"
            for c in source["components"]
            if not body.source_component_id
            or c["component_id"] == body.source_component_id
        }
        if body.target_facility_id:
            selected_target = f"SAMPLE:btx_facility:{body.target_facility_id}"
            if selected_target not in target_ids:
                raise HTTPException(
                    404, "Facility has no evidence-backed association to this objective"
                )
            target_ids = {selected_target}
    elif body.mode == "contact_candidates":
        target_ids = {
            f"SAMPLE:contact_candidate:{c['contact_id']}" for c in source["contacts"]
        }
    else:
        target_ids = set()
    response.headers["Cache-Control"] = "private, no-store"
    query = RouteQuery(
        "SAMPLE",
        f"SAMPLE:account:{body.source_account_id}",
        frozenset(target_ids),
        body.mode,
        body.as_of or datetime.now(UTC).date(),
        frozenset(accounts),
        body.source_component_id,
        body.target_component_id,
        body.depth,
    )
    try:
        result = RelationshipIntelligenceService(sample).ranked_routes(
            query,
            selected_path_id=body.selected_path_id,
            node_budget=body.node_budget,
            edge_budget=body.edge_budget,
            expanded_node_ids=body.expanded_node_ids,
            context_page=body.context_page,
            expected_graph_revision=body.expected_graph_revision,
            include_record_context=body.include_record_context,
        )
        if not target_ids:
            result["reason"] = (
                "No documented person-to-person introduction is established."
                if body.mode == "documented_access"
                else "No evidence-backed target is available for this objective."
            )
        result["query_options"] = {
            "components": [
                {"id": c["component_id"], "label": c["name"]}
                for c in source["components"]
            ],
            "target_components": [
                {"id": c["component_id"], "label": c["name"]}
                for c in sample.commercial_ledgers.get(body.target_account_id, {}).get(
                    "components", []
                )
            ],
            "accounts": [
                {"id": aid, "label": accounts[aid].legal_name}
                for aid in sorted(sample.commercial_ledgers)
                if aid != body.source_account_id
            ],
        }
        scoped_accounts = {body.source_account_id, body.target_account_id} - {None}
        result["related_intelligence"] = [
            {
                "event_id": item["id"],
                "account_id": item.get("account_id"),
                "assessment": item["business_briefing"],
            }
            for item in intelligence_signals(runtime)
            if item.get("account_id") in scoped_accounts
            and item.get("business_briefing")
        ]
        result["intelligence_boundary"] = (
            "Assessments provide pursuit context only; they do not create or strengthen relationship edges."
        )
        return result
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
