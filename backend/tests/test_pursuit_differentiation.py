"""SAMPLE pursuit narratives must not collapse into one cloned score pattern."""

from btx_omni.modules.commercial.opportunities import account_opportunities
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.named_company_cases import CUSTOMERS, PURSUITS


def test_named_pursuits_have_distinct_evidence_derived_scores():
    sample = enhance_environment(build_sample_environment())
    rows = {aid: account_opportunities(sample, aid)[0] for aid in (*CUSTOMERS, *PURSUITS)}
    pwin = {aid: row["pwin"]["score"] for aid, row in rows.items()}
    delivery = {aid: row["delivery_feasibility"] for aid, row in rows.items()}

    assert all(score is not None for score in pwin.values())
    assert len(set(pwin.values())) >= 4
    assert max(pwin.values()) - min(pwin.values()) >= 20
    # The mature customer's decision-authority access, incumbent position, and
    # repeated accepted SAMPLE deliveries legitimately put it above the 75-point
    # upper bound that was drafted for less-established pursuits.
    assert 75 < pwin["lockheed-martin"] <= 90
    assert all(20 <= score <= 75 for aid, score in pwin.items() if aid != "lockheed-martin")

    assert all(result["score"] is not None for result in delivery.values())
    assert len({result["band"] for result in delivery.values()}) >= 3
    assert all(result["band"] in {"C", "B", "B+", "A"} for result in delivery.values())
    # A B+ must be earned under the unchanged rubric, not authored as a label.
    assert all(result["score"] >= 78 for result in delivery.values() if result["band"] == "B+")
    assert delivery["rocket-lab-usa"]["score"] is not None
    assert delivery["rocket-lab-usa"]["factors"][1]["points"] == 25
