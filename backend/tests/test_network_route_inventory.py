"""HTTP privacy matrix with valid requests, positive controls and transport stubs."""
import json
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from network_route_inventory import HIDDEN_OPERATIONS, OPERATIONS
from sqlalchemy import create_engine, insert
from test_communications_settings import RecordingDelivery
from test_network_behavioral_privacy import CANARIES
from test_network_projection import sample

from btx_omni.api.session import principal
from btx_omni.core.config import Settings
from btx_omni.domain.work import ApprovalStatus, Principal, PrincipalRole
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.persistence import models
from btx_omni.persistence.network_import import NetworkImportRepository

NOW = datetime(2026, 9, 20, tzinfo=UTC)
ACTORS = [
    Principal("seller-1", "Fake", PrincipalRole.MANAGER, "other-tenant"),
    Principal("other-user", "Fake", PrincipalRole.MANAGER, "tenant-a"),
    Principal("seller-1", "Fake", "DENIED_TEST_ROLE", "tenant-a"),
    Principal("seller-1", "Fake", PrincipalRole.MANAGER, None),
    Principal("seller-1", "Fake", PrincipalRole.MANAGER, "tenant-a"),
]


@dataclass
class FakeCollectionRun:
    source_id: str = "fake"
    failures: tuple[str, ...] = ()


def test_route_inventory_is_complete():
    from btx_omni.app import app
    actual = {f"{method.upper()} {path}" for path, methods in app.openapi()["paths"].items()
              for method in methods if method in {"get", "post", "patch", "put", "delete"}}
    assert actual == set(OPERATIONS)
    assert len(actual) == 79
    def flattened(routes, prefix=""):
        for route in routes:
            if hasattr(route, "original_router"):
                yield from flattened(route.original_router.routes, prefix + route.include_context.prefix)
            elif hasattr(route, "path"):
                yield prefix + route.path, getattr(route, "methods", ())

    declared = {f"{method} {path}" for path, methods in flattened(app.routes) if path.startswith("/api/")
                for method in methods if method not in {"HEAD", "OPTIONS"}}
    assert declared == set(OPERATIONS) | set(HIDDEN_OPERATIONS)


@pytest.mark.parametrize("actor", ACTORS, ids=["wrong-tenant", "non-owner", "no-role", "no-tenant", "owner"])
def test_all_classified_operations_with_real_requests(tmp_path, monkeypatch, caplog, actor, record_property):
    import btx_omni.app as app_module
    from btx_omni.api import actions, communications, monitor
    from btx_omni.modules.markets.registry import BY_ID

    caplog.set_level(logging.INFO)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'privacy.db'}", environment="production",
                        ai_provider="gemini", gemini_api_key="fake-local-testing-only", action_salesperson_token="fake-local-code", action_manager_token="fake-admin-code",
                        monitor_operator_token="fake-operator-code")
    engine = create_engine(settings.database_url)
    models.metadata.create_all(engine)
    environment = sample()
    environment = replace(environment, crm_companies=tuple(
        replace(company, owner_id="fake-crm-owner") for company in environment.crm_companies))
    with engine.begin() as conn:
        conn.execute(insert(models.accounts).values(id="honeywell", name="Honeywell", relationship="PROSPECT"))
    path = tmp_path / "fake.csv"
    path.write_text("First Name,Last Name,URL,Company,Position,Connected On\n"
                    f"{CANARIES[0]},,{CANARIES[1]},Honeywell,{CANARIES[2]},2026-09-01\n", encoding="utf-8")
    repo = NetworkImportRepository(engine, environment.watch_profiles)
    batch = repo.import_file(path, tenant_id="tenant-a", owner_user_id="seller-1", owner_name="Fake Owner",
                            exported_at=NOW, apply=True)
    monkeypatch.setattr(app_module, "runtime", app_module.runtime)
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    app = app_module.create_app()
    runtime = app_module.runtime
    runtime.sample = environment
    settings.monitor_durable_state_enabled = True
    runtime.monitor.repository = MonitorRepository(engine)
    app.dependency_overrides[principal] = lambda: actor
    statuses = {}
    manager = Principal(actor.user_id, "Fake", PrincipalRole.MANAGER, actor.tenant_id)
    from btx_omni.ai.contracts import LanguageProviderError, ProviderStatus
    from btx_omni.ai.gemini import GeminiProvider
    captured_prompts = []

    def model_transport(self, prompt, generation_config):
        captured_prompts.append(prompt)
        raise LanguageProviderError(ProviderStatus.UNAVAILABLE)

    monkeypatch.setattr(GeminiProvider, "_generate_response", model_transport)
    # External delivery never leaves this process. Repository fixtures represent
    # public records only; the actual network repository and route code are real.
    monkeypatch.setattr(communications, "UnconfiguredDeliveryAdapter", RecordingDelivery)
    monkeypatch.setattr(runtime.monitor.repository, "event_document", lambda *a, **k: {"id": "fake-event", "canonical_account_ids": []})
    monkeypatch.setattr(runtime.monitor.repository, "intelligence_assessment_history", lambda *a, **k: [])
    monkeypatch.setattr(runtime.monitor.repository, "federal_assessment_by_id", lambda *a: {"id": "fake-assessment", "version": 1, "is_current": True, "projection": {"title": "Fake assessment"}})
    monkeypatch.setattr(runtime.reference_fields, "version", lambda *a: {"version_id": "a" * 64, "fields": []})
    monkeypatch.setattr(runtime.markets, "detail", lambda *a, **k: {"series_id": next(iter(BY_ID)), "observations": []})
    monkeypatch.setattr(monitor.CandidatePromotionService, "promote", lambda *a, **k: SimpleNamespace(
        candidate={"id": "fake-candidate"}, account=SimpleNamespace(account={"id": "fake-account"}), created=False))
    monkeypatch.setattr(monitor.ProgramCandidatePromotionService, "promote", lambda *a, **k: SimpleNamespace(
        candidate={"id": "fake-candidate"}, program=SimpleNamespace(program={"id": "fake-program"}), created=False))
    monkeypatch.setattr(runtime.monitor, "collect", lambda *a, **k: FakeCollectionRun())
    monkeypatch.setattr(runtime.monitor, "collect_all", lambda *a, **k: (FakeCollectionRun(),))
    with TestClient(app, base_url="https://backend.test", raise_server_exceptions=False) as client:
        for ordinal, (operation, classification) in enumerate((OPERATIONS | HIDDEN_OPERATIONS).items()):
            method, route = operation.split(" ", 1)
            url = route.replace("{account_id}", "honeywell")
            body, params = {}, {}
            headers = {"X-BTX-Monitor-Operator-Token": "fake-operator-code"}
            if "{collection}" in url:
                url = url.replace("{collection}", "contacts")
                params["limit"] = 100
            for key, value in {"version_id": "a" * 64, "series_id": next(iter(BY_ID)), "event_id": "fake-event",
                               "assessment_id": "fake-assessment", "candidate_id": "fake-candidate", "source_id": "federal_register"}.items():
                url = url.replace("{" + key + "}", value)
            if route.startswith("/api/session"):
                signed = client.post("/api/session/sign-in", json={"access_code": "fake-local-code"})
                assert signed.status_code == 200
                headers["X-CSRF-Token"] = signed.json()["csrf_token"]
                body = {"access_code": "fake-local-code"}
            if route == "/api/relationships/query":
                body = {"source_account_id": "honeywell", "mode": "contact_candidates"}
            if route == "/api/omni":
                body = {"account_id": "honeywell", "question": "Explain contacts and relationships"}
            if "{run_id}" in url:
                run_id = runtime.omni_runs.start(actor_id=actor.user_id, request={"question": "Fake"}, now=NOW)
                runtime.omni_runs.finish(run_id, actor_id=actor.user_id, result={"content": "Fake answer"}, now=NOW)
                url = url.replace("{run_id}", run_id)
            if route == "/api/actions" and method == "POST":
                body = {"account_id": "honeywell", "title": "Fake privacy action"}
            if "{action_id}" in url and "/commercial/" not in url:
                action = runtime.work.create(account_id="honeywell", title=f"Fake privacy action {ordinal}", principal=replace(manager, user_id="fake-requester") if route.endswith("/approval") else manager,
                                             approval_required=route.endswith("/approval"), occurred_at=NOW)
                url = url.replace("{action_id}", action.id)
                body = {"expected_version": action.version}
                if method == "PATCH":
                    body["title"] = "Fake edited action"
                if route.endswith("/status"):
                    body["status"] = "IN_PROGRESS"
                if route.endswith("/approval"):
                    body["decision"] = "APPROVED"
                if route.endswith(("/crm-proposal-decision", "/crm-execute")):
                    workflow = actions._crm_workflow(runtime)
                    proposal = workflow.preview(action.id, expected_version=1, principal=manager, now=NOW)
                    body = {"proposal_id": proposal["proposal_id"], "decision": "APPROVED"}
                    if route.endswith("/crm-execute"):
                        decision = workflow.decide(action.id, proposal["proposal_id"], decision="APPROVED", expected_decision_id=None, principal=manager, now=NOW)
                        body = {"proposal_id": proposal["proposal_id"], "expected_decision_id": decision["decision_id"], "idempotency_key": "fake-execute"}
                        params["confirmed"] = True
            if "/subtasks" in route:
                if "{subtask_id}" in url:
                    action = runtime.work.change_subtask(action.id, title="Fake subtask", principal=manager,
                        occurred_at=NOW, expected_version=action.version, idempotency_key=f"fake-child-{ordinal}")
                    url = url.replace("{subtask_id}", action.subtasks[0].id)
                body = {"expected_version": action.version, "title": "Fake subtask edit", "idempotency_key": f"fake-edit-{ordinal}"}
            if route in {"/api/omni/chat", "/api/omni/chat/stream"}:
                body = {"account_id": "honeywell", "question": "Explain contacts and relationships"}
            if "{identifier}" in url:
                from btx_omni.api.omni_chat import repository
                chat = repository(runtime)
                now = datetime.now(UTC)
                thread = chat.create(actor, now)
                run_id = runtime.omni_runs.start(actor_id=actor.user_id, request={"question": "Fake"}, now=now)
                chat.append(thread["id"], actor, now, version=thread["version"], turns=[{"role": "assistant", "response": {"run_id": run_id, "content": "Fake answer"}}])
                url = url.replace("{identifier}", thread["id"])
                body = {"title": "Fake renamed conversation"} if method == "PATCH" else {"run_id": run_id, "rating": "up"}
            if "/suggestions/" in route or "{receipt_id}" in url:
                suggestions = actions._suggestions(runtime, actor)
                suggestion = next(item for item in suggestions if not item["dismissed"] and not item["conversion_blocked"])
                url = url.replace("{suggestion_id}", suggestion["id"])
                body = {"expected_revision": suggestion["revision"]}
                if route.endswith("/feedback"):
                    body.update(reason="NOT_RELEVANT", idempotency_key=f"fake-feedback-{ordinal}")
                if "{receipt_id}" in url:
                    receipt = runtime.work_feedback.append(user_id=actor.user_id, suggestion_id=suggestion["id"], account_id=suggestion["account_id"], reason="NOT_RELEVANT", note="", now=NOW, idempotency_key="fake-receipt", expected_feedback_id=None)
                    url = url.replace("{receipt_id}", receipt["id"])
                    body = {"idempotency_key": "fake-undo"}
            if "/commercial/follow-ups/" in route:
                from btx_omni.modules.work.commercial_followup import followup_preview
                ledger = environment.commercial_ledgers["honeywell"]
                commercial_action = ledger["actions"][0]["action_id"]
                url = url.replace("{action_id}", commercial_action)
                preview = followup_preview(ledger, account_id="honeywell", action_id=commercial_action,
                                           revision=environment.commercial_revision, principal=actor, work=runtime.work)
                body = {"preview_token": preview["preview_token"]}
            if route == "/api/communications" and method == "POST":
                body = {"account_id": "honeywell", "subject": "Fake subject", "body": "Fake content"}
            if route == "/api/communications/assist":
                body = {"account_id": "honeywell", "instruction": "Summarize public facts"}
            if "{draft_id}" in url:
                draft = runtime.communications.create(account_id="honeywell", subject="Fake subject", body="Fake content", recipients=("fake@example.invalid",), principal=manager, occurred_at=NOW)
                if route.endswith("/send"):
                    draft = runtime.communications.decide(draft.id, ApprovalStatus.APPROVED, expected_version=1, principal=manager, occurred_at=NOW)
                url = url.replace("{draft_id}", draft.id)
                body = {"expected_version": draft.version}
                if method == "PATCH":
                    body["body"] = "Fake edit"
                if route.endswith("/approval"):
                    body["decision"] = "APPROVED"
                if route.endswith("/assist"):
                    body["instruction"] = "Summarize public facts"
                if route.endswith("/send"):
                    params = {"expected_version": draft.version, "confirmed": True, "idempotency_key": "fake-send"}
            if route.startswith("/api/omni/memories"):
                body = {"kind": "ANSWER_STYLE", "content": "Fake preference", "ttl_days": 14}
                if "{memory_id}" in url:
                    memory = runtime.memory.save(user_id=actor.user_id, account_id=None, now=NOW, **body)
                    url = url.replace("{memory_id}", memory["id"])
                    body["expected_version"] = 1
                    if route.endswith("/delete"):
                        body = {"expected_version": 1}
                else:
                    body["idempotency_key"] = "fake-memory"
            if route == "/api/itineraries/current" and method == "POST":
                body = {"title": "Fake trip", "stops": [], "idempotency_key": "fake-trip"}
            if route == "/api/planning/shortlist":
                body = {"account_id": "honeywell", "kind": "RESEARCH", "objective": "Fake research objective", "target_date": "2026-10-01", "active": True, "idempotency_key": "fake-shortlist"}
            if "/planning/partnerships/" in route:
                body = {"designated": True, "reason": "Fake review designation", "idempotency_key": "fake-partnership"}
            response = client.request(method, url, params=params, headers=headers, **({"json": body} if method != "GET" else {}))
            statuses[operation] = {"classification": classification, "status": response.status_code}
            allowed = actor == ACTORS[-1] and (route == "/api/relationships/query" or route.endswith("/commercial/{collection}"))
            if allowed:
                assert CANARIES[0] in response.text, operation
            else:
                assert not any(value in response.text for value in CANARIES), operation
        record_property("route_matrix", json.dumps(statuses, sort_keys=True))
        # Specific authorization denials are valid responses, never missing fixtures.
        role_denials = {
            "GET /api/monitor/candidates", "GET /api/monitor/health", "GET /api/monitor/sources",
            "POST /api/actions/{action_id}/approval", "POST /api/actions/{action_id}/crm-execute",
            "POST /api/actions/{action_id}/crm-proposal-decision", "POST /api/communications/{draft_id}/approval",
            "POST /api/planning/partnerships/{account_id}",
        } if actor.role == "DENIED_TEST_ROLE" else set()
        expected_denials = role_denials | {"POST /api/monitor/collect/{source_id}"}
        failures = {key: value for key, value in statuses.items()
                    if value["status"] != (403 if key in expected_denials else
                                           204 if key.endswith("/dismiss") else 200)}
        assert failures == {}
    assert not any(value in caplog.text for value in CANARIES)
    assert captured_prompts, "Real model prompts must reach the stub transport"
    assert not any(value in json.dumps(captured_prompts) for value in CANARIES)
    repo.purge_batch(batch["batch_id"], tenant_id="tenant-a", apply=True)
    assert repo.visible_rows(ACTORS[-1]) == ()
    for application_engine in (engine, runtime.network_imports.engine):
        for compiled in (application_engine._compiled_cache or {}).values():
            assert not any(value in repr(compiled.params) for value in CANARIES)
