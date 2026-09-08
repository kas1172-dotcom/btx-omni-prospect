import pytest

from btx_omni.core.config import Settings
from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.persistence.import_commercial_sample import (
    ACCOUNT_CROSSWALK,
    import_release_sample,
    load_release_sample,
)
from btx_omni.providers.sample.environment import build_sample_environment


def test_release_runtime_input_retains_exact_eleven_identities_and_financial_invariants():
    package = load_release_sample()
    accounts = {a.id: a for a in build_sample_environment().accounts}
    assert len(package['accounts']) == 11
    assert package['commercial_as_of'] == '2026-08-31'
    for account in package['accounts']:
        validate_commercial_account(account)
        target = accounts[ACCOUNT_CROSSWALK[account['account_id']]]
        assert target.domain in account['identity']['legacy_identity']['official_domains']
        assert len({r['period'] for r in account['monthly_commercial_history']}) == 12
        assert account['public_events'] == []


def test_release_import_wrong_mode_destination_and_missing_review_fail_before_connection(monkeypatch):
    def prohibited(*_, **__):
        raise AssertionError('Unsafe import must not connect')
    monkeypatch.setattr('btx_omni.persistence.import_commercial_sample.create_engine', prohibited)
    settings = Settings(_env_file=None, database_url='postgresql+psycopg://test@127.0.0.1/disposable')
    for kwargs in ({}, {'expected_host': 'another-host', 'expected_database': 'disposable'},
                   {'apply': True, 'expected_host': '127.0.0.1', 'expected_database': 'disposable'}):
        with pytest.raises(ValueError):
            import_release_sample(settings, **kwargs)
    with pytest.raises(ValueError, match='SAMPLE'):
        import_release_sample(settings.model_copy(update={'data_mode': 'CONNECTED'}))
