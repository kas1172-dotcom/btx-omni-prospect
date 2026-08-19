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


def upgrade() -> None:
    op.add_column("btx_facilities", Column("country", String(8)))
    op.add_column("btx_facilities", Column("source_url", Text))
    op.add_column("btx_facilities", Column("source_type", String(80)))


def downgrade() -> None:
    op.drop_column("btx_facilities", "source_type")
    op.drop_column("btx_facilities", "source_url")
    op.drop_column("btx_facilities", "country")
