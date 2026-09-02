from btx_omni.modules.commercial.read import CommercialReadService
from btx_omni.providers.sample.environment import build_sample_environment


def test_commercial_snapshot_preserves_canonical_identity_and_sample_truth() -> None:
    snapshot = CommercialReadService(build_sample_environment()).account_snapshot("lockheed-martin")
    assert snapshot.canonical_account_id == "lockheed-martin"
    assert snapshot.source_states["commercial"] == {"data_mode": "SAMPLE", "source_state": "AVAILABLE"}
    assert snapshot.source_states["paperless"] == {"data_mode": "SAMPLE", "source_state": "AVAILABLE"}
    assert snapshot.source_states["crm"] == {"data_mode": "SAMPLE", "source_state": "AVAILABLE"}
    assert all(item.account_id == "lockheed-martin" for item in snapshot.quotes)


def test_no_linked_provider_record_is_not_provider_unavailability() -> None:
    snapshot = CommercialReadService(build_sample_environment()).account_snapshot("huxwrx")
    assert snapshot.source_states["crm"] == {"data_mode": "SAMPLE", "source_state": "NO_LINKED_DATA"}
    assert snapshot.crm["companies"] == ()


def test_source_availability_is_independent_per_provider_without_live_calls() -> None:
    service = CommercialReadService(build_sample_environment(), source_states={"crm": ("CONNECTED", "UNAVAILABLE"), "paperless": ("CONNECTED", "NOT_CONFIGURED")})
    snapshot = service.account_snapshot("lockheed-martin")
    assert snapshot.canonical_account_id == "lockheed-martin"
    assert snapshot.source_states["commercial"] == {"data_mode": "SAMPLE", "source_state": "AVAILABLE"}
    assert snapshot.source_states["crm"] == {"data_mode": "CONNECTED", "source_state": "UNAVAILABLE"}
    assert snapshot.source_states["paperless"] == {"data_mode": "CONNECTED", "source_state": "NOT_CONFIGURED"}
