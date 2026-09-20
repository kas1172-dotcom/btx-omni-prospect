from datetime import timedelta
from pathlib import Path

from btx_omni.core.clock import as_of_datetime, evidence_state, relative_date
from btx_omni.core.config import get_settings


def test_fixed_default_and_relative_dates(monkeypatch):
    monkeypatch.setenv('DEMO_AS_OF_DATE', '2026-09-20')
    get_settings.cache_clear()
    try:
        assert relative_date(6) == '2026-09-26'
        recorded = as_of_datetime()
        assert evidence_state(recorded, as_of=recorded + timedelta(days=2)) == 'CURRENT'
        assert evidence_state(recorded, as_of=recorded + timedelta(days=2, seconds=1)) == 'STALE'
        monkeypatch.setenv('DEMO_AS_OF_DATE', '2026-09-23')
        get_settings.cache_clear()
        assert evidence_state(recorded) == 'STALE'
    finally:
        get_settings.cache_clear()


def test_no_wall_clock_in_scoring_or_fixture_generators():
    root = Path(__file__).parents[1] / 'src' / 'btx_omni'
    paths = [*root.joinpath('modules/scoring').rglob('*.py'), *root.joinpath('providers').rglob('*.py')]
    paths += [root / name for name in ('api/actions.py', 'api/account_planning.py', 'api/itineraries.py',
                                      'modules/intelligence/technical_fit.py', 'modules/intelligence/governed_explanations.py')]
    for path in paths:
        text = path.read_text(encoding='utf-8')
        assert not any(token in text for token in ('datetime.now(', 'date.today(', 'time.time(')), path
