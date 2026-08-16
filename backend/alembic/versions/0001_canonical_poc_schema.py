"""canonical POC schema

Revision ID: 0001_canonical_poc
"""
from alembic import op
from btx_omni.persistence.models import metadata

revision = "0001_canonical_poc"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    metadata.drop_all(op.get_bind())
