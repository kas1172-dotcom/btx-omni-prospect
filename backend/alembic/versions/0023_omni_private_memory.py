"""Principal-private expiring preferences; no commercial or public-fact ownership."""
from alembic import op
from btx_omni.persistence.omni_memory import omni_user_memory

revision = "0023_omni_private_memory"
down_revision = "0022_commercial_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    omni_user_memory.create(op.get_bind())


def downgrade():
    omni_user_memory.drop(op.get_bind())
