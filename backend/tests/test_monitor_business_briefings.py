from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from test_commercial_persistence import importer_package

from btx_omni.ai.contracts import BusinessBriefingResult, ProviderStatus
from btx_omni.core.config import Settings
from btx_omni.modules.assistant.orchestration import OmniOrchestrator
from btx_omni.modules.commercial.projection import project_commercial_records
from btx_omni.monitor.briefs import (
    BriefSynthesisBatch,
    SignalBrief,
    governed_content_hash,
    synthesize_signal_brief_with_status,
)
from btx_omni.monitor.business_briefings import (
    apply_evidence_package,
    assemble_evidence_package,
    requires_technical_investigation,
)
from btx_omni.monitor.contracts import CollectionRun
from btx_omni.monitor.repository import MonitorRepository
from btx_omni.monitor.worker import run_worker
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.persistence.models import metadata
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


class Repository:
    def event_document(self, event_id, *, include_research=False):
        return {
            "event_id": event_id,
            "observation_id": "observation-1",
            "source_id": "official",
            "source_url": "https://example.com/source",
            "title": "Official development",
            "content_hash": "a" * 64,
            "document": {
                "extraction_status": "TEXT_EXTRACTED",
                "extraction_complete": True,
                "checksum_sha256": "b" * 64,
                "retrieved_at": NOW.isoformat(),
                "publication_date": "2026-08-29",
                "final_url": "https://example.com/source",
                "passages": [
                    {
                        "id": "passage-1",
                        "text": "Official evidence describes the scoped development.",
                    }
                ],
            },
            "research": None,
        }


def brief(account_id: str, *, event_type="REGULATORY_APPROVAL", program_id=None):
    return SignalBrief(
        id=f"event-{account_id}",
        headline="Public development",
        what_happened="Official development",
        why_it_may_matter="pending",
        canonical_account_ids=(account_id,),
        canonical_program_id=program_id,
        markets=("Medical",),
        publication_timestamp=datetime(2026, 8, 29, tzinfo=UTC),
        collection_timestamp=NOW,
        freshness="STALE",
        evidence_ids=("passage-1",),
        source_url="https://example.com/source",
        source_system="official",
        data_mode="LIVE_PUBLIC",
        resolution_state="RESOLVED",
        seller_promotion_state="WITHHELD_STALE",
        what_to_watch="pending",
        recommended_action=None,
        missing_fields=(),
        seller_summary="pending",
        event_type=event_type,
    )


def imported_environment(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'business-brief.db'}")
    metadata.create_all(engine)
    repository = CommercialImportRepository(engine)
    base = build_sample_environment()
    repository.import_package(
        importer_package(), {"test-account": "honeywell"}, base, apply=True
    )
    revision, records = repository.snapshot()
    environment = project_commercial_records(base, records, revision=revision)
    engine.dispose()
    return environment


def test_medtronic_public_approval_remains_informational_without_scoped_btx_link():
    package = assemble_evidence_package(
        brief("medtronic"),
        environment=build_sample_environment(),
        repository=Repository(),
        now=NOW,
    )
    rendered = apply_evidence_package(brief("medtronic"), package)
    assert package["commercial_relevance_state"] == "INFORMATIONAL"
    assert rendered.priority_eligible is False and rendered.recommended_action is None
    assert package["public_evidence"][0]["source_url"] == "https://example.com/source"
    assert "does not establish" in rendered.why_it_may_matter
    assert "No seller action is established" in rendered.seller_summary
    assert "governed public update" not in rendered.seller_summary.casefold()


def test_exact_existing_customer_program_context_is_specific_and_revision_sensitive(
    tmp_path,
):
    environment = imported_environment(tmp_path)
    candidate = brief("honeywell", event_type="CONTRACT_AWARD", program_id="p")
    first = assemble_evidence_package(
        candidate, environment=environment, repository=Repository(), now=NOW
    )
    assert first["commercial_relevance_state"] == "ESTABLISHED_COMMERCIAL_RELEVANCE"
    assert first["commercial_record_scope"] == "EXACT_PROGRAM"
    assert first["priority_eligible"] is True
    projected = apply_evidence_package(candidate, first)
    assert "Next:" in projected.seller_summary
    assert first["recommended_action"] in projected.seller_summary
    changed_ledgers = deepcopy(environment.commercial_ledgers)
    changed_ledgers["honeywell"]["order_lines"][0]["line_total_minor"] += 100
    changed = assemble_evidence_package(
        candidate,
        environment=replace(environment, commercial_ledgers=changed_ledgers),
        repository=Repository(),
        now=NOW,
    )
    assert changed["input_revision"] != first["input_revision"]
    assert changed["action_rationale"] != first["action_rationale"]
    unrelated = dict(environment.commercial_ledgers)
    unrelated["unrelated-account"] = {"not_used": True}
    unaffected = assemble_evidence_package(
        candidate,
        environment=replace(environment, commercial_ledgers=unrelated),
        repository=Repository(),
        now=NOW,
    )
    assert unaffected["input_revision"] == first["input_revision"]


def test_risk_briefing_uses_account_history_without_universal_technical_gate(tmp_path):
    environment = imported_environment(tmp_path)
    candidate = brief("honeywell", event_type="REGULATORY_CHANGE")
    package = assemble_evidence_package(
        candidate, environment=environment, repository=Repository(), now=NOW
    )
    assert package["commercial_relevance_state"] == "ESTABLISHED_ACCOUNT_REVIEW"
    assert package["recommended_action"].startswith("Review the cited notice")
    assert requires_technical_investigation("REGULATORY_CHANGE") is False
    assert requires_technical_investigation("CONTRACT_AWARD") is True


def test_missing_passages_fail_closed_instead_of_showing_completed_intelligence():
    empty = SimpleNamespace(event_document=lambda *args, **kwargs: None)
    package = assemble_evidence_package(
        brief("medtronic"),
        environment=build_sample_environment(),
        repository=empty,
        now=NOW,
    )
    rendered = apply_evidence_package(brief("medtronic"), package)
    assert rendered.analysis_status == "INCOMPLETE"
    assert rendered.priority_eligible is False
    assert any("passage" in item for item in rendered.material_uncertainties)


def test_structured_language_can_improve_prose_but_not_governed_relevance():
    class Provider:
        configured = True
        name = "fixture"
        config = SimpleNamespace(model="fixture")

        def synthesize_business_brief(self, request):
            return BusinessBriefingResult(
                "Specific development",
                "A supported change",
                "Account-specific implication",
                None,
                "Keep informational until scope is established.",
                ("Program scope remains unknown.",),
                ("passage-1",),
                "fixture",
                "fixture",
            )

    base = brief("medtronic")
    governed = apply_evidence_package(
        base,
        assemble_evidence_package(
            base,
            environment=build_sample_environment(),
            repository=Repository(),
            now=NOW,
        ),
    )
    result = synthesize_signal_brief_with_status(governed, Provider())
    assert result.provider_status is ProviderStatus.AVAILABLE
    assert result.brief.headline == "Specific development"
    assert result.brief.commercial_relevance_state == "INFORMATIONAL"
    assert result.brief.priority_eligible is False
    assert result.brief.recommended_action is None


def test_assessment_history_reuses_unchanged_input_and_versions_material_change(
    tmp_path,
):
    engine = create_engine(f"sqlite:///{tmp_path / 'assessment-history.db'}")
    metadata.create_all(engine)
    repository = MonitorRepository(engine)
    base = {
        "event_id": "event-1",
        "account_id": "honeywell",
        "business_unit_id": None,
        "source_revision": "a" * 64,
        "generation_status": "DETERMINISTIC_READY",
        "provider": None,
        "model": None,
        "created_at": NOW,
    }
    first = repository.save_intelligence_assessment(
        **base, input_revision="1" * 64, projection={"headline": "First"}
    )
    replay = repository.save_intelligence_assessment(
        **base, input_revision="1" * 64, projection={"headline": "First"}
    )
    changed = repository.save_intelligence_assessment(
        **base, input_revision="2" * 64, projection={"headline": "Changed"}
    )
    history = repository.intelligence_assessment_history(
        "event-1", account_id="honeywell"
    )
    assert replay["id"] == first["id"] and len(history) == 2
    assert (
        changed["version"] == 2
        and history[0]["is_current"] is True
        and history[1]["is_current"] is False
    )
    engine.dispose()


def test_omni_selects_the_event_assessment_for_the_requested_account_context():
    environment = build_sample_environment()
    records = tuple(
        {
            "id": "shared-event",
            "account_id": account_id,
            "title": f"{account_id} development",
            "kind": "CONTRACT_AWARD",
            "evidence_ids": (f"evidence-{account_id}",),
            "business_briefing": {
                "headline": f"Specific {account_id} assessment",
                "what_happened": f"Change scoped to {account_id}",
                "why_it_may_matter": f"Implication for {account_id}",
                "recommended_action": f"Review {account_id}",
                "material_uncertainties": (),
                "references": (),
                "evidence_package": {"commercial_records": ()},
            },
        }
        for account_id in ("boeing", "honeywell")
    )
    response = OmniOrchestrator().answer(
        environment,
        account_id=None,
        question="Why does this matter?",
        observed_at=NOW,
        context={
            "surface": "INTELLIGENCE",
            "selected_event_id": "shared-event",
            "active_filters": {"account_id": "honeywell"},
        },
        intelligence_events=records,
    )
    assert response.account_id == "honeywell"
    assert "Specific honeywell assessment" in response.content
    assert "Specific boeing assessment" not in response.content


def test_persistence_receipts_do_not_invalidate_unchanged_brief_synthesis():
    candidate = brief("honeywell")
    packaged = apply_evidence_package(
        candidate,
        assemble_evidence_package(
            candidate,
            environment=build_sample_environment(),
            repository=Repository(),
            now=NOW,
        ),
    )
    persisted = replace(
        packaged,
        headline="Gemini seller headline",
        why_it_may_matter="Gemini seller explanation",
        recommended_action="Gemini phrasing for the governed action",
        assessment_id="assessment-1",
        assessment_version=2,
        generation_status="GEMINI_ASSISTED",
    )
    assert governed_content_hash(persisted) == governed_content_hash(packaged)


def test_source_timeout_is_reported_but_does_not_block_successful_source_processing(
    monkeypatch,
):
    processed = []

    class RepositoryWithLock:
        @staticmethod
        def operational_lock():
            return nullcontext(True)

    class Source:
        @staticmethod
        def available(_settings):
            return True, None

    class Monitor:
        def __init__(self):
            self.repository = RepositoryWithLock()
            self.registry = {"slow": Source(), "fast": Source()}

        @staticmethod
        def collect(source_id, **_kwargs):
            return CollectionRun(
                f"run-{source_id}",
                source_id,
                NOW,
                NOW,
                None,
                failures=("DEADLINE_EXCEEDED",) if source_id == "slow" else (),
            )

    class Runtime:
        def __init__(self):
            self.monitor = Monitor()
            self.markets = SimpleNamespace(
                worker_refresh=lambda **_kwargs: {"status": "DISABLED"}
            )
            self.technical_decomposition = SimpleNamespace()

        @staticmethod
        def environment():
            return build_sample_environment()

        @staticmethod
        def observed_at():
            return NOW

    def projected(*_args, **_kwargs):
        processed.append("projected")
        return ()

    def synthesized(*_args, **_kwargs):
        processed.append("synthesized")
        return BriefSynthesisBatch(0, 0, 0, 0, (), False)

    monkeypatch.setattr(
        "btx_omni.monitor.worker.PocRuntime", lambda _settings: Runtime()
    )
    monkeypatch.setattr(
        "btx_omni.monitor.worker.get_ai_provider",
        lambda _config: SimpleNamespace(configured=False),
    )
    monkeypatch.setattr("btx_omni.monitor.worker.signal_briefs_for_monitor", projected)
    monkeypatch.setattr(
        "btx_omni.monitor.worker.process_signal_brief_synthesis", synthesized
    )
    monkeypatch.setattr(
        "btx_omni.monitor.worker.procurement_projection",
        lambda _runtime: {"active": {"opportunities": []}},
    )
    report, code = run_worker(
        Settings(
            _env_file=None,
            monitor_mode="live",
            monitor_durable_state_enabled=True,
            monitor_worker_sources="slow,fast",
            monitor_worker_max_seconds=60,
            monitor_technical_decomposition_cap=0,
            market_refresh_enabled=False,
        )
    )
    assert [item["source_id"] for item in report["runs"]] == ["slow", "fast"]
    assert "synthesized" in processed
    assert report["failed_sources"] == ("slow",)
    assert report["status"] == "FAILED" and code == 1
