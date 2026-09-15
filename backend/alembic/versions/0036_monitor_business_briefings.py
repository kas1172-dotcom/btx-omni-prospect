"""Persist governed event-specific Monitor business briefing projections."""
import sqlalchemy as sa

from alembic import op

revision = "0036_monitor_business_briefings"
down_revision = "0035_account_planning"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("monitor_brief_syntheses", sa.Column("projection", sa.Text()))
    op.add_column("monitor_brief_syntheses", sa.Column("source_revision", sa.String(64)))
    op.add_column("monitor_brief_syntheses", sa.Column("input_revision", sa.String(64)))
    op.create_table(
        "monitor_intelligence_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("context_key", sa.String(400), nullable=False),
        sa.Column("event_id", sa.String(160), nullable=False),
        sa.Column("account_id", sa.String(100)),
        sa.Column("business_unit_id", sa.String(100)),
        sa.Column("input_revision", sa.String(64), nullable=False),
        sa.Column("source_revision", sa.String(64)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("projection", sa.Text(), nullable=False),
        sa.Column("generation_status", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("context_key", "version", name="uq_monitor_assessment_context_version"),
    )
    op.create_index("ix_monitor_assessment_current", "monitor_intelligence_assessments", ["context_key", "is_current"])


def downgrade():
    raise RuntimeError("Retain governed Monitor briefing lineage; restore a compatible reviewed backup instead.")
