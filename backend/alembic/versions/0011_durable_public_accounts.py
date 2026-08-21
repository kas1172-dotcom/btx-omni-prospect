"""Add durable canonical public Prospect Account foundation."""

from alembic import op
from btx_omni.persistence.models import durable_public_accounts

revision = "0011_durable_public_accounts"
down_revision = "0010_monitor_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    durable_public_accounts.create(op.get_bind())


def downgrade() -> None:
    durable_public_accounts.drop(op.get_bind())
