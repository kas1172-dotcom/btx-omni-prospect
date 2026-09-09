from btx_omni.monitor.catalog import MonitorCatalog, governed_phrase_in_text
from btx_omni.monitor.ontology import ResolutionState
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity


def test_live_nasa_astronomy_words_do_not_resolve_short_company_aliases():
    profiles = (
        AccountWatchProfile('ge-aerospace', 'GE Aerospace', ('GE',)),
        AccountWatchProfile('itt', 'ITT Inc.', ('ITT',)),
        AccountWatchProfile('pi', 'Physik Instrumente', ('PI',)),
        AccountWatchProfile('vat', 'VAT Group', ('VAT',)),
    )
    # Regression for real local run 317e1498: substring matching attached these
    # four companies to astronomy prose and even source JSON metadata.
    text = 'The Otherworldly Geology of Vasquez Rocks. Image and picture explanation written by an astronomer. Recent observations of Saturn.'
    result = MonitorCatalog(profiles).resolve_subjects(text, source_url='https://science.nasa.gov/image-article/saturn')
    assert all(item.canonical_account_id is None for item in result)
    assert all(item.state is ResolutionState.UNRESOLVED for item in result)


def test_company_phrase_boundaries_preserve_full_names_and_punctuation():
    assert governed_phrase_in_text('KLA Corporation', 'KLA Corporation: component inspection update.')
    assert governed_phrase_in_text('Lockheed Martin', 'A Lockheed Martin-led program')
    assert not governed_phrase_in_text('Eaton', 'Wheaton facility')
    assert not governed_phrase_in_text('PI', 'PI is a principal investigator')
    assert not governed_phrase_in_text('GE', 'image')


def test_short_company_alias_requires_structured_identity_or_owned_publisher():
    profile = AccountWatchProfile('kla', 'KLA Corporation', ('KLA',), domain='kla.com')
    assert MonitorCatalog((profile,)).resolve_subjects('KLA announces equipment', source_url='https://www.kla.com/news')[0].canonical_account_id == 'kla'
    assert MonitorCatalog((profile,)).resolve_subjects('KLA Corporation announces equipment')[0].canonical_account_id == 'kla'
    assert resolve_entity('KLA', (profile,)).canonical_account_id == 'kla'  # explicit structured mention remains valid


def test_identifier_namespace_and_unknown_values_cannot_cross_resolve():
    profile = AccountWatchProfile('account', 'Canonical Company', uei='00123', cage='04567', sec_cik='000890')
    assert resolve_entity('unknown', (profile,), source_identifiers=(('uei', '04567'),)).state is ResolutionState.UNRESOLVED
    assert resolve_entity('unknown', (profile,), source_identifiers=(('uei', '123'),)).state is ResolutionState.UNRESOLVED
    assert resolve_entity('unknown', (profile,), source_identifiers=(('cage', ''),)).state is ResolutionState.UNRESOLVED
    assert resolve_entity('unknown', (profile,), source_identifiers=(('cik', '890'),)).canonical_account_id == 'account'
    assert resolve_entity('unknown', (profile,), source_identifiers=(('uei', '00123'),)).canonical_account_id == 'account'
