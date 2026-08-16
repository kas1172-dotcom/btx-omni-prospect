"""add decisioning scoring and commercial alerts

Revision ID: 0002_decisioning
Revises: 0001_canonical_poc
"""
from alembic import op
from btx_omni.persistence.models import (
    commercial_alerts,
    score_assessments,
    score_configurations,
)

revision = "0002_decisioning"
down_revision = "0001_canonical_poc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    score_configurations.create(bind)
    score_assessments.create(bind)
    commercial_alerts.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    commercial_alerts.drop(bind)
    score_assessments.drop(bind)
    score_configurations.drop(bind)
