"""Prepare only the dedicated, repository-local Profiles SAMPLE database."""
from pathlib import Path

from sqlalchemy import create_engine

from btx_omni.persistence import models
from btx_omni.persistence.commercial_import import CommercialImportRepository
from btx_omni.persistence.import_commercial_sample import (
    ACCOUNT_CROSSWALK,
    load_release_sample,
)
from btx_omni.persistence.reference_fields import ReferenceFieldRepository
from btx_omni.providers.research.reference_data import load_private_reference_fields
from btx_omni.providers.sample.environment import build_sample_environment


def main():
    destination = Path(__file__).resolve().parents[1] / 'redesign-e2e.sqlite'
    engine = create_engine(f'sqlite:///{destination.as_posix()}')
    # Register all application tables without constructing a runtime or contacting a provider.
    from btx_omni.api.runtime import PocRuntime  # noqa: F401
    models.metadata.create_all(engine)
    sample = build_sample_environment()
    repository = CommercialImportRepository(engine)
    package = load_release_sample()
    dry = repository.import_package(package, ACCOUNT_CROSSWALK, sample)
    result = repository.import_package(package, ACCOUNT_CROSSWALK, sample, apply=True,
                                       expected_revision=dry['prior_revision'])
    references = ReferenceFieldRepository(engine)
    fields = load_private_reference_fields()
    ids = {account.id for account in sample.accounts}
    reviewed = references.import_package(fields, canonical_account_ids=ids)
    references.import_package(fields, canonical_account_ids=ids, apply=True,
                              expected_revision=reviewed['prior_revision'])
    print({'database': str(destination), 'created': result['created'], 'updated': result['updated'],
           'unchanged': result['unchanged'], 'accounts': result['accounts']})
    engine.dispose()


if __name__ == '__main__':
    main()
