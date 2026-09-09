from copy import deepcopy
from datetime import UTC, datetime

import pytest
from test_actions_v2 import OTHER, SELLER, durable_service
from test_commercial_ledger import small_ledger

from btx_omni.modules.work.commercial_followup import confirm_followup, followup_preview
from btx_omni.modules.work.service import (
    ActionConflictError,
    ActionForbiddenError,
    ActionNotFoundError,
    WorkService,
)
from btx_omni.persistence.actions import SqlActionRepository


def test_preview_confirm_restart_replay_and_scope(tmp_path):
    account = small_ledger()
    account["actions"] = [{"action_id": "case-a", "title": "Review acceptance", "status": "OPEN",
                           "due_date": "2026-09-09", "evidence_record_ids": ["v"]}]
    work = durable_service(tmp_path)
    args = {"account_id": "boeing", "action_id": "case-a", "revision": "revision-1",
            "principal": SELLER, "work": work}
    preview = followup_preview(account, **args)
    assert not work.list() and preview["external_write"] is False
    assert preview["proposal"]["owner_id"] == SELLER.user_id
    confirm_args = {**args, "preview_token": preview["preview_token"], "occurred_at": datetime(2026, 9, 8, tzinfo=UTC)}
    created = confirm_followup(account, **confirm_args)
    restarted = WorkService(SqlActionRepository(work.repository.engine))
    assert confirm_followup(account, **{**confirm_args, "work": restarted}) == created
    assert len(restarted.list()) == len(restarted.audit(created.id)) == 1
    assert created.context_referents == (("commercial_action", "case-a"),)
    with pytest.raises(ActionForbiddenError):
        followup_preview(account, **{**args, "principal": OTHER})
    with pytest.raises(ActionConflictError, match="changed"):
        confirm_followup(account, **{**confirm_args, "revision": "revision-2"})
    changed = deepcopy(account)
    changed["actions"][0]["title"] = "A different commitment"
    with pytest.raises(ActionConflictError, match="changed"):
        confirm_followup(changed, **confirm_args)
    changed["actions"][0]["evidence_record_ids"] = ["another-account-record"]
    with pytest.raises(ActionConflictError, match="evidence"):
        followup_preview(changed, **args)
    with pytest.raises(ActionNotFoundError):
        followup_preview(account, **{**args, "action_id": "unknown"})
