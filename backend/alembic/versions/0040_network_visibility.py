"""Add explicit imported-network visibility ownership."""
import sqlalchemy as sa
from alembic import op

revision = "0040_network_visibility"
down_revision = "0039_network_connections"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("network_import_batches") as batch:
        batch.add_column(sa.Column("visibility", sa.String(32), nullable=False, server_default="owner_only"))
        batch.add_column(sa.Column("owner_user_id", sa.String(128)))
        batch.create_check_constraint("ck_network_batch_visibility", "visibility IN ('owner_only', 'tenant_shared')")


def downgrade():
    raise RuntimeError("Retain imported network visibility lineage; restore a reviewed backup instead.")
