"""Safe build declarations and read-only schema compatibility, not release acceptance."""
import re
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

REPOSITORY = 'kas1172-dotcom/btx-omni-prospect'
REQUIRED_SCHEMA_REVISION = '0033_monitor_research_journal'


def build_identity(settings) -> dict:
    # Only validated public identifiers can leave the server. Never echo arbitrary
    # environment values (including accidentally misconfigured secret values).
    sha = settings.release_sha if re.fullmatch(r'[0-9a-f]{40}', settings.release_sha) else None
    tree = settings.release_tree if re.fullmatch(r'[0-9a-f]{40}', settings.release_tree) else None
    clean = settings.release_worktree == 'clean'
    return {'repository': REPOSITORY, 'commit_sha': sha, 'git_tree': tree,
            'worktree': settings.release_worktree if settings.release_worktree in {'clean', 'dirty'} else 'unknown',
            'identity_state': 'DECLARED_CLEAN_BUILD' if sha and tree and clean else 'UNVERIFIED_BUILD',
            'required_schema_revision': REQUIRED_SCHEMA_REVISION,
            'authority': 'BUILD_DECLARATION; independently compare hosting image and Git tree before acceptance.'}


def database_compatibility(engine) -> dict:
    revision = None
    state = 'UNAVAILABLE'
    try:
        with engine.connect() as connection:
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL statement_timeout = '2000ms'"))
                connection.execute(text("SET LOCAL lock_timeout = '1000ms'"))
            rows = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        if len(rows) == 1 and re.fullmatch(r'[A-Za-z0-9_]{1,128}', rows[0]):
            revision = rows[0]
            state = 'CURRENT' if revision == REQUIRED_SCHEMA_REVISION else 'MIGRATION_MISMATCH'
        else:
            state = 'AMBIGUOUS_SCHEMA'
    except SQLAlchemyError:
        # Do not serialize exception messages, DSNs or provider credentials.
        pass
    return {'state': state, 'migration_revision': revision, 'required_revision': REQUIRED_SCHEMA_REVISION,
            'checked_at': datetime.now(UTC).isoformat()}
