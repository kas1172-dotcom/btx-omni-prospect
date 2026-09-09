"""Retain collection-stage funnel evidence without inventing historical metrics."""
import sqlalchemy as sa

from alembic import op

revision = "0024_monitor_funnel"
down_revision = "0023_omni_private_memory"
branch_labels = None
depends_on = None


def upgrade():
    # The original bootstrap migration creates current shared metadata. Fresh
    # databases therefore already have this column; populated upgrades do not.
    existing = next((column for column in sa.inspect(op.get_bind()).get_columns("monitor_collection_runs") if column["name"] == "funnel"), None)
    if existing is not None:
        if not isinstance(existing["type"], sa.Text) or not existing["nullable"]:
            raise RuntimeError("Existing Monitor funnel column has an incompatible contract")
        return
    op.add_column("monitor_collection_runs", sa.Column("funnel", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("monitor_collection_runs", "funnel")
