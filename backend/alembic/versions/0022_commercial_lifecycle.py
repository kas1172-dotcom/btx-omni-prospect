"""Add missing commercial lifecycle owners; retain existing catalog/transactions."""
from sqlalchemy import Column, Text, inspect

from alembic import op
from btx_omni.persistence.commercial_schema import (
    LIFECYCLE_TABLES,
    SOURCE_PAYLOAD_TABLES,
    commercial_account_profiles,
    commercial_import_ownership,
    commercial_import_runs,
)

revision = "0022_commercial_lifecycle"
down_revision = "0021_monitor_entity_candidate_resolutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in SOURCE_PAYLOAD_TABLES:
        # Earlier catalog migrations use the shared Table definitions when
        # creating a fresh database; populated upgrades still need the column.
        existing = {column["name"] for column in inspect(op.get_bind()).get_columns(table.name)}
        if "source_payload" not in existing:
            op.add_column(table.name, Column("source_payload", Text))
    for table in (
        commercial_account_profiles, *LIFECYCLE_TABLES.values(),
        commercial_import_ownership, commercial_import_runs,
    ):
        table.create(op.get_bind())


def downgrade() -> None:
    for table in reversed((
        commercial_account_profiles, *LIFECYCLE_TABLES.values(),
        commercial_import_ownership, commercial_import_runs,
    )):
        table.drop(op.get_bind())
    for table in reversed(SOURCE_PAYLOAD_TABLES):
        op.drop_column(table.name, "source_payload")
