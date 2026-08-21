"""add BTX facility location-source metadata

Revision ID: 0009_btx_facility_location_metadata
Revises: 0008_commercial_and_edges
"""
from sqlalchemy import Column, String, Text

from alembic import op

revision = "0009_btx_facility_location_metadata"
down_revision = "0008_commercial_and_edges"
branch_labels = None
depends_on = None

# Alembic creates its legacy version table with VARCHAR(32).  Revision IDs in
# this chain became longer at this revision, so PostgreSQL must widen the table
# before Alembic stamps this revision after upgrade() returns.
ALEMBIC_VERSION_ID_CAPACITY = 128


def _widen_legacy_alembic_version_column() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=String(32),
        type_=String(ALEMBIC_VERSION_ID_CAPACITY),
        existing_nullable=False,
    )


def upgrade() -> None:
    _widen_legacy_alembic_version_column()
    op.add_column("btx_facilities", Column("country", String(8)))
    op.add_column("btx_facilities", Column("source_url", Text))
    op.add_column("btx_facilities", Column("source_type", String(80)))


def downgrade() -> None:
    op.drop_column("btx_facilities", "source_type")
    op.drop_column("btx_facilities", "source_url")
    op.drop_column("btx_facilities", "country")
