"""Add durable Monitor organization and program candidates."""
from alembic import op
from btx_omni.persistence.models import (
    monitor_organization_candidates,
    monitor_program_candidates,
)

revision = "0010_monitor_candidates"
down_revision = "0009_btx_facility_location_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    monitor_organization_candidates.create(op.get_bind())
    monitor_program_candidates.create(op.get_bind())


def downgrade() -> None:
    monitor_program_candidates.drop(op.get_bind())
    monitor_organization_candidates.drop(op.get_bind())
