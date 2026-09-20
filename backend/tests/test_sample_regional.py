from decimal import Decimal

from btx_omni.api.accounts import accounts
from btx_omni.api.map import map_data
from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.modules.scoring.prospect_fit import prospect_fit_projection
from btx_omni.providers.sample.enhancement import enhance_environment
from btx_omni.providers.sample.environment import build_sample_environment
from btx_omni.providers.sample.regional import IDS


def test_j1_regional_cohort_has_exact_pins_and_directory_parity(tmp_path):
    from sqlalchemy import create_engine

    from btx_omni.api.runtime import PocRuntime
    from btx_omni.core.config import Settings
    from btx_omni.persistence.models import metadata
    url = f'sqlite:///{tmp_path / "regional.db"}'
    engine = create_engine(url)
    metadata.create_all(engine)
    engine.dispose()
    runtime = PocRuntime(Settings(_env_file=None, database_url=url, sample_enhancement_enabled=True, monitor_mode='disabled'))
    result = map_data(runtime=runtime)
    markers = [r for r in result['accounts'] if r['account_id'] in IDS]
    directory = [r for r in accounts(runtime)['accounts'] if r['id'] in IDS]
    assert len(markers) == len(directory) == 9
    assert result['sample_journey']['origin']
    assert result['sample_journey']['travel_times'] is None
    assert {r['account_id'] for r in markers} == {r['id'] for r in directory}
    assert len({r['industry'] for r in markers}) == 6
    assert any(r['id'] == 'btx-facility:demo-btx-southwest' for r in result['btx_facilities'])
    for row in markers:
        assert row['sample_context']['synthetic'] and row['sample_context']['contact_gap']
        assert row['sample_context']['programs'] and row['naics_assignments']
        assert -90 <= Decimal(row['coordinates']['latitude']) <= 90
    assert all(r['truth_state'] == 'FICTIONAL_SAMPLE' for r in directory)


def test_private_aerospace_prospect_fit_80_and_low_distribution():
    sample = enhance_environment(build_sample_environment())
    for aid, target in [('demo-regional-aero', 80), ('demo-regional-medical-prospect', 31.25)]:
        account = next(a for a in sample.accounts if a.id == aid)
        result = prospect_fit_projection(account, applicable=True)
        assert result.score == Decimal(str(target))
        assert not account.public_contacts
    for aid in IDS:
        validate_commercial_account(sample.commercial_ledgers[aid])
