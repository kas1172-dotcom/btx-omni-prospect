import re
from pathlib import Path

from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.enhancement import enhance_environment


def test_contract_required_counts_are_reached() -> None:
    contract = Path(__file__).parents[2] / "docs" / "product" / "SAMPLE_DATA_CONTRACT.md"
    rows = re.findall(r"\|\s*(\w+)\s*\|\s*(\d+)\s*\|", contract.read_text())
    assert rows
    environment = enhance_environment(build_sample_environment())
    for name, minimum in rows:
        assert len(getattr(environment, name)) >= int(minimum), name
