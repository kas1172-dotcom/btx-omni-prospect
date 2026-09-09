from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from btx_omni.core.config import Settings
from btx_omni.core.release import (
    REQUIRED_SCHEMA_REVISION,
    build_identity,
    database_compatibility,
)


def test_build_declaration_is_explicit_and_does_not_expose_invalid_values():
    settings = Settings(_env_file=None, release_sha='secret-not-a-sha', release_tree='', release_worktree='private-token')
    report = build_identity(settings)
    assert report['identity_state'] == 'UNVERIFIED_BUILD'
    assert report['commit_sha'] is None and report['worktree'] == 'unknown'
    assert 'secret' not in str(report) and 'private-token' not in str(report)
    clean = build_identity(settings.model_copy(update={'release_sha': 'a' * 40, 'release_tree': 'b' * 40, 'release_worktree': 'clean'}))
    assert clean['identity_state'] == 'DECLARED_CLEAN_BUILD'
    assert 'independently' in clean['authority']


def test_database_requires_exact_single_head_and_real_check_time():
    engine = create_engine('sqlite://')
    assert database_compatibility(engine)['state'] == 'UNAVAILABLE'
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0021_monitor_entity_candidate_resolutions')"))
    assert database_compatibility(engine)['state'] == 'MIGRATION_MISMATCH'
    before = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(text('UPDATE alembic_version SET version_num=:head'), {'head': REQUIRED_SCHEMA_REVISION})
    report = database_compatibility(engine)
    assert report['state'] == 'CURRENT'
    assert before <= datetime.fromisoformat(report['checked_at']) <= datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO alembic_version VALUES ('second_head')"))
    assert database_compatibility(engine)['state'] == 'AMBIGUOUS_SCHEMA'


def test_required_revision_matches_actual_alembic_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    assert ScriptDirectory.from_config(Config('alembic.ini')).get_heads() == [REQUIRED_SCHEMA_REVISION]
