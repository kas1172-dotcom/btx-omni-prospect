from dataclasses import replace

import pytest
from sqlalchemy import update
from test_commercial_persistence import importer_package, storage  # noqa: F401

from btx_omni.api.runtime import PocRuntime
from btx_omni.core.config import Settings
from btx_omni.modules.commercial.crm_mapping import retained_crm_mapping
from btx_omni.persistence import models
from btx_omni.providers.sample.environment import build_sample_environment


def test_assignment_provenance_is_stable_not_synthetic_load_time():
    first, second = build_sample_environment(), build_sample_environment()
    assert retained_crm_mapping(first.crm_companies, 'boeing') == retained_crm_mapping(second.crm_companies, 'boeing')
    owner, payload = retained_crm_mapping(first.crm_companies, 'boeing')
    assert owner == next(c.owner_id for c in first.crm_companies if c.account_id == 'boeing')
    assert payload['owner_provenance']['observed_at'] is None
    assert payload['owner_provenance']['date_status'] == 'SOURCE_ASSIGNMENT_DATE_UNAVAILABLE'
    assert retained_crm_mapping(first.crm_companies, 'honeywell')[0] is None
    company = next(c for c in first.crm_companies if c.account_id == 'boeing')
    with pytest.raises(ValueError, match='Ambiguous'):
        retained_crm_mapping((company, replace(company, id='another-company')), 'boeing')


def test_import_preserves_supported_owner_and_runtime_reads_persisted_mapping(storage):  # noqa: F811
    repo, environment, url = storage
    package = importer_package()
    package['accounts'][0]['identity'] = {'display_name': 'Boeing', 'legacy_identity': {'official_domains': ['boeing.com']}}
    crosswalk = {'test-account': 'boeing'}
    repo.import_package(package, crosswalk, environment, apply=True)
    expected_owner, expected_mapping = retained_crm_mapping(environment.crm_companies, 'boeing')
    assert repo.crm_mappings()['boeing'] == {'id': 'crm:boeing', 'owner_id': expected_owner, 'properties': expected_mapping}
    # Reloading the source catalog cannot manufacture a new provenance time.
    replay = repo.import_package(package, crosswalk, build_sample_environment(), apply=True)
    assert replay['created'] == replay['updated'] == replay['removed'] == 0
    runtime = PocRuntime(Settings(database_url=url, commercial_durable_state_enabled=True, _env_file=None))
    company = next(c for c in runtime.environment().crm_companies if c.account_id == 'boeing')
    assert company.owner_id == expected_owner
    profile_revision = repo.revision()
    # Explicit isolated negative fixture: persisted retraction, not a provider
    # success. Mapping changes invalidate the runtime even if finances did not.
    with repo.engine.begin() as connection:
        connection.execute(update(models.crm_companies).where(models.crm_companies.c.id == 'crm:boeing').values(owner_id=None))
    assert repo.revision() == profile_revision
    assert next(c for c in runtime.environment().crm_companies if c.account_id == 'boeing').owner_id is None
    assert repo.accounts()['boeing'] == package['accounts'][0]
