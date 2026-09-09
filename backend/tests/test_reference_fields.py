from copy import deepcopy

import pytest
from sqlalchemy import create_engine

from btx_omni.persistence.models import metadata
from btx_omni.persistence.reference_fields import ReferenceFieldRepository
from btx_omni.providers.research.reference_data import load_private_reference_fields


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "references.db"}')
    metadata.create_all(engine)
    yield ReferenceFieldRepository(engine)
    engine.dispose()


def test_all_source_fields_replay_restart_and_corrected_versions(repository):
    package = load_private_reference_fields()
    ids = {r['canonical_account_id'] for r in package['rows']}
    dry = repository.import_package(package, canonical_account_ids=ids)
    assert dry['created'] == len(package['rows']) and repository.list(next(iter(ids)))['total'] == 0
    first = repository.import_package(package, canonical_account_ids=ids, apply=True, expected_revision=dry['prior_revision'])
    replay = repository.import_package(package, canonical_account_ids=ids, apply=True, expected_revision=first['current_revision'])
    assert replay['created'] == replay['updated'] == replay['removed'] == replay['canonical_accounts_created'] == 0
    assert replay['unchanged'] == len(package['rows'])
    actual = {}
    reopened = ReferenceFieldRepository(create_engine(repository.engine.url))
    try:
        for account in ids:
            offset = 0
            while True:
                page = reopened.list(account, offset=offset)
                actual.update({r['row_key']: r for r in page['items']})
                if page['next_offset'] is None:
                    break
                offset = page['next_offset']
        assert set(actual) == {r['row_key'] for r in package['rows']}
        for row in package['rows']:
            assert actual[row['row_key']]['fields'] == row['fields']
    finally:
        reopened.engine.dispose()
    changed = deepcopy(package)
    row = changed['rows'][0]
    old = actual[row['row_key']]
    row['fields'][0]['value'] = 'Explicit test correction'
    corrected = repository.import_package(changed, canonical_account_ids=ids, apply=True, expected_revision=replay['current_revision'])
    assert corrected['updated'] == 1 and corrected['created'] == 0
    historic = repository.version(row['canonical_account_id'], old['version_id'])
    assert historic['fields'] == old['fields'] and not historic['is_current']
    assert repository.version('foreign-account', old['version_id']) is None
    with pytest.raises(ValueError, match='changed after review'):
        repository.import_package(package, canonical_account_ids=ids, apply=True, expected_revision=replay['current_revision'])


@pytest.mark.parametrize('mutation', ['identity', 'lineage', 'missing_column', 'formula', 'nonfinite', 'group'])
def test_invalid_references_cannot_mutate_canonical_state(repository, mutation):
    package = load_private_reference_fields()
    ids = {r['canonical_account_id'] for r in package['rows']}
    field = package['rows'][0]['fields'][0]
    if mutation == 'identity':
        package['rows'][0]['canonical_account_id'] = 'not-an-existing-account'
    elif mutation == 'lineage':
        field['source_cell'] = 'Z999'
    elif mutation == 'missing_column':
        package['rows'][0]['fields'].pop()
    elif mutation == 'formula':
        field['source_formula'] = '=1+1'
    elif mutation == 'nonfinite':
        field['value'] = float('nan')
    else:
        field['group'] = 'official_score'
    with pytest.raises(ValueError):
        repository.import_package(package, canonical_account_ids=ids)
    assert repository.list(next(iter(ids)))['total'] == 0
