from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine

from btx_omni.app import create_app
from btx_omni.domain.work import ApprovalStatus, Principal, PrincipalRole
from btx_omni.integrations.communications import DeliveryPreview
from btx_omni.modules.communications.service import (
    CommunicationConflictError,
    CommunicationForbiddenError,
    CommunicationService,
)
from btx_omni.persistence.communications import SqlCommunicationRepository
from btx_omni.persistence.models import metadata

NOW = datetime(2026, 8, 31, tzinfo=UTC)
SELLER = Principal("seller-1", "Seller", PrincipalRole.SALESPERSON)
MANAGER = Principal("manager-1", "Manager", PrincipalRole.MANAGER)


class RecordingDelivery:
    def __init__(self) -> None:
        self.calls = 0

    def preview(self, draft):
        return DeliveryPreview(True, "TEST", len(draft.recipients), "Preview available")

    def send(self, draft, *, idempotency_key: str) -> str:
        self.calls += 1
        return f"receipt:{idempotency_key}"


def service(tmp_path) -> CommunicationService:
    engine = create_engine(f"sqlite:///{tmp_path / 'communications.db'}")
    metadata.create_all(engine)
    return CommunicationService(SqlCommunicationRepository(engine))


def test_draft_is_durable_and_distinct_from_action_or_send(tmp_path) -> None:
    first = service(tmp_path)
    draft = first.create(
        account_id="boeing",
        subject="Review public evidence",
        body="Draft outreach for human review.",
        recipients=(),
        principal=SELLER,
        occurred_at=NOW,
        evidence_ids=("FAA_BOEING",),
        idempotency_key="draft-one",
    )
    restarted = service(tmp_path)
    loaded = restarted.list(SELLER)[0]
    assert loaded.id == draft.id and loaded.status.value == "DRAFT"
    assert loaded.approval_status is ApprovalStatus.PENDING
    assert restarted.history(draft.id, SELLER)[0].event == "CREATED"


def test_human_review_confirmation_and_idempotent_delivery(tmp_path) -> None:
    communications = service(tmp_path)
    draft = communications.create(
        account_id="boeing",
        subject="Approved note",
        body="Governed content",
        recipients=("verified@example.com",),
        principal=SELLER,
        occurred_at=NOW,
    )
    with pytest.raises(CommunicationForbiddenError):
        communications.decide(
            draft.id, ApprovalStatus.APPROVED, principal=SELLER, occurred_at=NOW
        )
    approved = communications.decide(
        draft.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW
    )
    delivery = RecordingDelivery()
    with pytest.raises(CommunicationConflictError, match="confirmation"):
        communications.send(
            approved.id,
            principal=MANAGER,
            occurred_at=NOW,
            confirmed=False,
            idempotency_key="send-one",
            delivery=delivery,
        )
    sent = communications.send(
        approved.id,
        principal=MANAGER,
        occurred_at=NOW,
        confirmed=True,
        idempotency_key="send-one",
        delivery=delivery,
    )
    replay = communications.send(
        approved.id,
        principal=MANAGER,
        occurred_at=NOW,
        confirmed=True,
        idempotency_key="send-one",
        delivery=delivery,
    )
    assert sent.status.value == replay.status.value == "SENT" and delivery.calls == 1


def test_edit_resets_review_and_structured_audit(tmp_path) -> None:
    communications = service(tmp_path)
    draft = communications.create(
        account_id="boeing",
        subject="First",
        body="First body",
        recipients=(),
        principal=SELLER,
        occurred_at=NOW,
    )
    communications.decide(
        draft.id, ApprovalStatus.APPROVED, principal=MANAGER, occurred_at=NOW
    )
    edited = communications.edit(
        draft.id, body="Human revision", principal=MANAGER, occurred_at=NOW
    )
    assert edited.approval_status is ApprovalStatus.PENDING
    assert [event.event for event in communications.history(draft.id, MANAGER)] == [
        "CREATED",
        "APPROVED",
        "EDITED",
    ]


@pytest.mark.asyncio
async def test_api_rejects_fabricated_recipient_and_excludes_secrets() -> None:
    headers = {"X-BTX-Principal-Token": "development-salesperson"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        invented = await client.post(
            "/api/communications",
            headers=headers,
            json={
                "account_id": "boeing",
                "subject": "Hello",
                "body": "Governed draft",
                "recipients": ["invented@example.com"],
            },
        )
        settings = await client.get("/api/settings", headers=headers)
        self_promote = await client.patch(
            "/api/settings/role", headers=headers, json={"role": "MANAGER"}
        )
    assert invented.status_code == 422
    assert settings.status_code == 200 and self_promote.status_code == 404
    payload = settings.json()
    assert payload["principal"]["role"] == "SALESPERSON"
    assert "key" not in str(payload).casefold() and "token" not in str(payload).casefold()


@pytest.mark.asyncio
async def test_api_requires_manager_review_and_never_autosends() -> None:
    seller = {"X-BTX-Principal-Token": "development-salesperson"}
    manager = {"X-BTX-Principal-Token": "development-manager"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/communications",
            headers=seller,
            json={
                "account_id": "boeing",
                "subject": "Human review required",
                "body": "This remains a draft.",
                "idempotency_key": f"api-communications-governance-{uuid4()}",
            },
        )
        draft_id = created.json()["id"]
        seller_approval = await client.post(
            f"/api/communications/{draft_id}/approval",
            headers=seller,
            json={"decision": "APPROVED"},
        )
        approved = await client.post(
            f"/api/communications/{draft_id}/approval",
            headers=manager,
            json={"decision": "APPROVED"},
        )
        blocked = await client.post(
            f"/api/communications/{draft_id}/send",
            headers=manager,
            params={"confirmed": True, "idempotency_key": "api-send-one"},
        )
    assert created.status_code == 200 and created.json()["status"] == "DRAFT"
    assert seller_approval.status_code == 403
    assert approved.status_code == 200 and approved.json()["status"] == "READY"
    assert blocked.status_code == 409 and "recipient" in blocked.text.casefold()


@pytest.mark.asyncio
async def test_api_governed_draft_assist_is_a_nonpersistent_proposal() -> None:
    headers = {"X-BTX-Principal-Token": "development-salesperson"}
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        before = await client.get("/api/communications", headers=headers)
        proposal = await client.post(
            "/api/communications/assist",
            headers=headers,
            json={
                "account_id": "boeing",
                "instruction": "Draft a concise manager update.",
                "subject": "Boeing update",
                "body": "Existing governed draft.",
                "evidence_ids": ["ev-1"],
            },
        )
        after = await client.get("/api/communications", headers=headers)
    assert proposal.status_code == 200
    payload = proposal.json()
    assert payload["assisted"] is False and payload["provider_status"] == "NOT_CONFIGURED"
    assert payload["proposal"]["body"] == "Existing governed draft."
    assert before.json()["items"] == after.json()["items"]
