"""Preview and create a local follow-up through the existing authorized work owner."""
import json
from datetime import date, datetime
from hashlib import sha256

from btx_omni.domain.work import ActionPriority, Principal
from btx_omni.modules.commercial.evidence import resolve_commercial_evidence
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionNotFoundError,
    ActionPolicy,
    WorkService,
)


def followup_preview(account: dict, *, account_id: str, action_id: str,
                     revision: str, principal: Principal, work: WorkService) -> dict:
    source = next((a for a in account["actions"] if a["action_id"] == action_id), None)
    if source is None:
        raise ActionNotFoundError(action_id)
    evidence = source.get("evidence_record_ids", [])
    if not evidence or not all(resolve_commercial_evidence(account, eid) for eid in evidence):
        raise ActionConflictError("Resolve the follow-up's evidence before creating work.")
    if source["status"] not in {"OPEN", "IN_PROGRESS"}:
        raise ActionConflictError("This source follow-up is no longer open.")
    suggestion_id = f"commercial-follow-up:{account_id}:{action_id}"
    existing = work.repository.by_suggestion(suggestion_id)
    if existing:
        ActionPolicy.require_manage(principal, existing)
        if existing.account_id != account_id:
            raise ActionConflictError("Existing work has an incompatible account mapping.")
    proposal = {
        "account_id": account_id, "title": source["title"],
        "description": source.get("completion_criteria"),
        "owner_id": principal.user_id, "priority": "MEDIUM",
        "due_date": source.get("due_date"), "evidence_ids": evidence,
        "context_referents": [["commercial_action", action_id]],
        "source_suggestion_id": suggestion_id, "approval_required": False,
    }
    token = sha256(json.dumps([revision, principal.user_id, proposal], sort_keys=True).encode()).hexdigest()
    return {"proposal": proposal, "preview_token": token, "revision": revision,
            "destination": "Local Omni Prospect work queue", "external_write": False,
            "existing_work_id": existing.id if existing else None,
            "existing_work_status": existing.status.value if existing else None,
            "note": "Creates a review task, not a delivery commitment, buyer acceptance, email or HubSpot write. Priority defaults to medium; it is not the deterministic Action Priority index."}


def confirm_followup(account: dict, *, account_id: str, action_id: str,
                     revision: str, principal: Principal, work: WorkService,
                     preview_token: str, occurred_at: datetime):
    preview = followup_preview(account, account_id=account_id, action_id=action_id,
                               revision=revision, principal=principal, work=work)
    if preview["preview_token"] != preview_token:
        raise ActionConflictError("The proposal or account evidence changed; review a fresh preview.")
    proposal = {**preview["proposal"]}
    proposal["due_date"] = date.fromisoformat(proposal["due_date"]) if proposal["due_date"] else None
    proposal["priority"] = ActionPriority(proposal["priority"])
    proposal["evidence_ids"] = tuple(proposal["evidence_ids"])
    proposal["context_referents"] = tuple(tuple(r) for r in proposal["context_referents"])
    return work.create(**proposal, principal=principal, occurred_at=occurred_at,
                       idempotency_key=preview_token)
