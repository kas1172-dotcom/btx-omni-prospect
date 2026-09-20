from btx_omni.modules.commercial.briefing import commercial_briefing
from btx_omni.modules.commercial.ledger import validate_commercial_account
from btx_omni.providers.sample.enhancement import boeing_recovery
from btx_omni.providers.sample.expansion import add_boeing_expansion, expansion_context


def test_j5_public_signal_and_synthetic_history_join_without_inventing_supply():
    account = add_boeing_expansion(boeing_recovery())
    validate_commercial_account(account)
    brief = commercial_briefing(account, canonical_account_id='boeing', revision='demo')['expansion_context']
    assert len(brief['active_business_units']) == 2
    assert brief['current_quote_id'] in {q['quote_id'] for q in account['quotes']}
    assert brief['supplied_component_ids'] and brief['program_history']
    assert brief['qualification'] == 'UNKNOWN_NEED'
    assert 'not established' in brief['unsupported_link']
    event, observation = expansion_context()
    assert event.subject_entities[0].canonical_account_id == 'boeing'
    assert not event.provenance.synthetic
    assert observation.source_published_at.date().isoformat() == '2026-08-24'
