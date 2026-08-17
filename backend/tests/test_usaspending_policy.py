import json
from datetime import UTC, datetime

from btx_omni.core.config import Settings
from btx_omni.monitor.ontology import SellerRelevanceState
from btx_omni.monitor.resolution import AccountWatchProfile
from btx_omni.monitor.service import MonitorService
from btx_omni.monitor.sources import UsaSpendingAdapter
from btx_omni.monitor.usaspending import (
    normalize_usaspending_observation,
    recipient_query_names,
    targeted_profiles,
)


def _observation(payload: dict):
    payload.setdefault("generated_internal_id", "CONT_AWD_TEST_9700_-NONE-_-NONE-")
    return UsaSpendingAdapter().parse(json.dumps({"results": [payload]}).encode(), run_id="fixture-run")[0]


def _profiles() -> tuple[AccountWatchProfile, ...]:
    return (
        AccountWatchProfile("boeing", "Boeing", aliases=("The Boeing Company",), industries=("Commercial Aerospace",)),
        AccountWatchProfile("rocket-lab-usa", "Rocket Lab USA", subsidiaries=("Rocket Lab",), industries=("Space",)),
        AccountWatchProfile("medtronic", "Medtronic", industries=("Medical Device",)),
    )


def test_usaspending_exact_recipient_is_eligible_only_with_current_direct_evidence() -> None:
    observation = _observation({"Award ID": "A-1", "Recipient Name": "Boeing", "Description": "Aircraft component production award", "Award Amount": "250000", "Award Type Code": "A", "Action Date": "2026-08-10", "uiLink": "https://www.usaspending.gov/award/A-1"})

    decision = normalize_usaspending_observation(observation, profiles=_profiles(), now=datetime(2026, 8, 17, tzinfo=UTC))

    assert decision.event.seller_relevance_state is SellerRelevanceState.RESOLVED_ELIGIBLE
    assert decision.event.subject_entities[0].canonical_account_id == "boeing"
    assert decision.rejected is None


def test_usaspending_alias_subsidiary_is_ambiguous_and_not_seller_visible() -> None:
    observation = _observation({"Award ID": "A-2", "Recipient Name": "Rocket Lab", "Description": "Launch support award", "Award Amount": "250000", "Action Date": "2026-08-10", "uiLink": "https://www.usaspending.gov/award/A-2"})

    decision = normalize_usaspending_observation(observation, profiles=_profiles(), now=datetime(2026, 8, 17, tzinfo=UTC))

    assert decision.event.seller_relevance_state is SellerRelevanceState.AMBIGUOUS
    assert decision.event.subject_entities[0].canonical_account_id is None


def test_usaspending_incomplete_current_response_is_rejected_before_relevance() -> None:
    """The live endpoint may return a result row without action date or detail URL."""
    observation = _observation({"Award ID": "A-2b", "Recipient Name": "Boeing", "Description": "Award result", "Award Amount": "250000", "Action Date": None, "uiLink": None})

    decision = normalize_usaspending_observation(observation, profiles=_profiles(), now=datetime(2026, 8, 17, tzinfo=UTC))

    assert decision.event.seller_relevance_state is SellerRelevanceState.REJECTED
    assert decision.rejected and "MISSING_ACTION_DATE" in decision.rejected.reason


def test_usaspending_stale_and_irrelevant_awards_are_rejected() -> None:
    stale = _observation({"Award ID": "A-3", "Recipient Name": "Boeing", "Description": "Aircraft component production award", "Award Amount": "250000", "Action Date": "2025-12-01", "uiLink": "https://www.usaspending.gov/award/A-3"})
    irrelevant = _observation({"Award ID": "A-4", "Recipient Name": "Boeing", "Description": "Aircraft component production award", "Award Amount": "0", "Action Date": "2026-08-10", "uiLink": "https://www.usaspending.gov/award/A-4"})

    for observation in (stale, irrelevant):
        decision = normalize_usaspending_observation(observation, profiles=_profiles(), now=datetime(2026, 8, 17, tzinfo=UTC))
        assert decision.event.seller_relevance_state is SellerRelevanceState.REJECTED
        assert decision.rejected is not None


def test_usaspending_adapter_is_account_targeted_and_records_source_failure() -> None:
    requested: list[dict] = []

    def post(_url: str, body: bytes, _headers: dict[str, str]):
        requested.append(json.loads(body))
        return 500, b"{}", {}

    adapter = UsaSpendingAdapter(recipient_names=("Boeing",), post=post)
    service = MonitorService(Settings(_env_file=None, monitor_mode="live"), {"usaspending": adapter}, watch_profiles=_profiles())

    run = service.collect("usaspending")

    assert run.failures == ("HTTP_500",)
    assert requested[0]["filters"]["recipient_search_text"] == ["Boeing"]
    assert recipient_query_names(targeted_profiles(_profiles(), rich_account_ids={"boeing", "rocket-lab-usa"})) == ("Boeing", "Rocket Lab USA")


def test_usaspending_adapter_uses_documented_award_and_transaction_contracts() -> None:
    requests: list[tuple[str, dict]] = []

    def post(url: str, body: bytes, _headers: dict[str, str]):
        requests.append((url, json.loads(body)))
        if url.endswith("spending_by_award/"):
            return 200, json.dumps({"results": [{"generated_internal_id": "CONT_AWD_TEST_9700_-NONE-_-NONE-", "Award ID": "TEST", "Recipient Name": "The Boeing Company", "Award Amount": "500", "Description": "Search description", "Award Type": "D"}]}).encode(), {}
        return 200, json.dumps({"results": [{"action_date": "2026-08-10", "description": "Transaction description", "federal_action_obligation": "500", "type": "D"}]}).encode(), {}

    observation = UsaSpendingAdapter(recipient_names=("The Boeing Company",), post=post).collect(run_id="contract", settings=Settings(_env_file=None, monitor_mode="live"))[0]

    assert requests[0][0].endswith("spending_by_award/")
    assert requests[0][1]["fields"] == ["Award ID", "Description", "Award Amount", "Recipient Name", "Awarding Agency", "Awarding Sub Agency", "Award Type"]
    assert requests[1] == ("https://api.usaspending.gov/api/v2/transactions/", {"award_id": "CONT_AWD_TEST_9700_-NONE-_-NONE-", "page": 1, "limit": 1, "sort": "action_date", "order": "desc"})
    assert observation.source_published_at == datetime(2026, 8, 10, tzinfo=UTC)
    assert observation.raw_evidence.locator == "https://api.usaspending.gov/api/v2/awards/CONT_AWD_TEST_9700_-NONE-_-NONE-/"


def test_usaspending_noneligible_observations_remain_durable_but_do_not_project() -> None:
    payload = {"results": [{"generated_internal_id": "CONT_AWD_UNRELATED_9700_-NONE-_-NONE-", "Award ID": "A-5", "Recipient Name": "Unrelated Entity", "Description": "Award", "Award Amount": "100", "Award Type": "D"}]}
    adapter = UsaSpendingAdapter(recipient_names=("Boeing",), post=lambda url, _body, _headers: (200, json.dumps({"results": [{"action_date": "2026-08-10", "description": "Award", "federal_action_obligation": "100", "type": "D"}]} if url.endswith("transactions/") else payload).encode(), {}))
    service = MonitorService(Settings(_env_file=None, monitor_mode="live"), {"usaspending": adapter}, watch_profiles=_profiles())

    run = service.collect("usaspending")

    assert run.records_seen == 1
    assert next(iter(service.events.values())).seller_relevance_state is SellerRelevanceState.UNRESOLVED
