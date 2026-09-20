"""Exercise the HTTP boundary with persisted canaries and denied principals."""
import json
import logging
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from test_network_projection import sample

from btx_omni.ai.config import AiConfig
from btx_omni.ai.gemini import GeminiProvider
from btx_omni.api.session import principal
from btx_omni.core.config import Settings
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.modules.intelligence.governed_explanation_adapters import (
    relationship_path_request,
)
from btx_omni.persistence import models
from btx_omni.persistence.network_import import NetworkImportRepository

CANARIES = ("NETWORK_CANARY_PERSON_81", "https://example.invalid/NETWORK_CANARY_URL_81", "NETWORK_CANARY_TITLE_81")


@pytest.mark.parametrize("actor", [
    Principal("seller-1", "Test", PrincipalRole.SALESPERSON, "other-tenant"),
    Principal("other-user", "Test", PrincipalRole.SALESPERSON, "tenant-a"),
    # No governed role is currently contact-ineligible; exercise fail-closed handling
    # of an unknown role without adding it to the governed vocabulary.
    Principal("seller-1", "Test", "DENIED_TEST_ROLE", "tenant-a"),
    Principal("seller-1", "Test", PrincipalRole.SALESPERSON, None),
])
def test_json_routes_do_not_expose_denied_network(tmp_path, monkeypatch, caplog, actor, record_property):
    import btx_omni.app as app_module

    caplog.set_level(logging.INFO)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'privacy.db'}",
                        environment="production", commercial_durable_state_enabled=False,
                        monitor_durable_state_enabled=False, ai_provider="disabled")
    engine = create_engine(settings.database_url)
    models.metadata.create_all(engine)
    environment = sample()
    with engine.begin() as connection:
        connection.execute(insert(models.accounts).values(id="honeywell", name="Honeywell", relationship="PROSPECT"))
    path = tmp_path / "Connections.csv"
    path.write_text("First Name,Last Name,URL,Company,Position,Connected On\n"
                    f"{CANARIES[0]},,{CANARIES[1]},Honeywell,{CANARIES[2]},2026-09-01\n", encoding="utf-8")
    repository = NetworkImportRepository(engine, environment.watch_profiles)
    repository.import_file(path, tenant_id="tenant-a", owner_user_id="seller-1", owner_name="Fake Owner",
                           exported_at=datetime(2026, 9, 1, tzinfo=UTC), apply=True)
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    # create_app replaces the module singleton; restore it after this test so
    # the test database/runtime cannot leak into unrelated suite cases.
    monkeypatch.setattr(app_module, "runtime", app_module.runtime)
    app = app_module.create_app()
    app_module.runtime.sample = environment
    app.dependency_overrides[principal] = lambda: actor
    captured_prompts = []

    def capture_prompt(self, prompt, config):
        captured_prompts.append(prompt)
        raise ValueError("Test model transport disabled")

    monkeypatch.setattr(GeminiProvider, "_generate_text", capture_prompt)
    statuses = {}
    with TestClient(app, raise_server_exceptions=False) as client:
        app.dependency_overrides[principal] = lambda: Principal("seller-1", "Owner", PrincipalRole.SALESPERSON, "tenant-a")
        owner_response = client.post("/api/relationships/query", json={"source_account_id": "honeywell", "mode": "contact_candidates"})
        assert owner_response.status_code == 200
        assert CANARIES[0] in owner_response.text
        app.dependency_overrides[principal] = lambda: actor
        for route, methods in app.openapi()["paths"].items():
            url = re.sub(r"\{([^}]+)\}", lambda match: "honeywell" if match[1] in {"account_id", "customer_id"} else "missing-test-record", route)
            for method in methods:
                if method not in {"get", "post", "patch", "put", "delete"}:
                    continue
                body = {"source_account_id": "honeywell", "mode": "contact_candidates"} if route == "/api/relationships/query" else {}
                if route == "/api/omni":
                    body = {"account_id": "honeywell", "question": "Explain contacts and relationships"}
                response = client.request(method, url, **({"json": body} if method != "get" else {}))
                statuses[f"{method.upper()} {route}"] = response.status_code
                assert not any(value in response.text for value in CANARIES), f"Leak on {method} {route}"
        for mode in ("contact_candidates", "documented_access"):
            response = client.post("/api/relationships/query", json={"source_account_id": "honeywell", "mode": mode})
            assert response.status_code == 200, response.text
            assert not any(value in response.text for value in CANARIES)
    assert not any(value in caplog.text for value in CANARIES)
    assert not any(value in json.dumps(captured_prompts) for value in CANARIES)
    assert not any(value in repr(asdict(app_module.runtime.sample)) for value in CANARIES)
    # Inspect application-owned process dictionaries after an authorized read and
    # subsequent denied requests. The durable database is intentionally excluded.
    for module_name, module in tuple(sys.modules.items()):
        if module_name.startswith("btx_omni.") and module is not None:
            for name, value in vars(module).items():
                if "cache" in name.casefold() and isinstance(value, (dict, list, tuple, set)):
                    assert not any(canary in repr(value) for canary in CANARIES), f"Cache leak: {module_name}.{name}"
    assert repository.visible_rows(actor) == ()
    record_property("route_statuses", json.dumps(statuses, sort_keys=True))
    record_property("body_not_exercised", json.dumps({key: value for key, value in statuses.items() if value >= 400}, sort_keys=True))


def test_actual_governed_gemini_prompt_drops_imported_pii(monkeypatch):
    request = relationship_path_request({
        "path_id": "fake-path", "data_mode": "IMPORTED", "summary": CANARIES[0],
        "seller_rationale": CANARIES[2], "connection_label": CANARIES[1],
        "steps": [{"kind": "external_contact", "label": CANARIES[0]}],
    }, customer_id="honeywell")
    prompts = []

    def capture(self, prompt, config):
        prompts.append(prompt)
        return json.dumps({"summary": "Needs validation", "key_drivers": [], "limitations": [],
                           "what_to_consider": [], "evidence_ids": []})

    monkeypatch.setattr(GeminiProvider, "_generate_text", capture)
    GeminiProvider(AiConfig.from_settings(Settings(_env_file=None))).explain_governed_result(request)
    assert len(prompts) == 1
    assert all(value not in prompts[0] for value in CANARIES)
    assert "IMPORTED" in prompts[0]
