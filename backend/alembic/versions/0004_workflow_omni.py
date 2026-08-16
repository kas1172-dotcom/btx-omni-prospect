"""add workflow audit and bounded assistant turn persistence

Revision ID: 0004_workflow
Revises: 0003_intelligence
"""
from alembic import op
from btx_omni.persistence.models import assistant_turns, work_audit_events, work_items

revision = "0004_workflow"
down_revision = "0003_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    work_items.create(bind)
    work_audit_events.create(bind)
    assistant_turns.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    assistant_turns.drop(bind)
    work_audit_events.drop(bind)
    work_items.drop(bind)
