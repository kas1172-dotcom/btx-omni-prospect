"""Persist resumable federal collection coverage and routed assessments."""

import sqlalchemy as sa
from alembic import op

revision = "0038_federal_opportunity_pipeline"
down_revision = "0037_monitor_technical_hierarchy"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "federal_collection_checkpoints",
        sa.Column("source_id", sa.String(100), primary_key=True),
        sa.Column("query_key", sa.String(160), primary_key=True),
        sa.Column("query_value", sa.String(160), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("page_size", sa.Integer(), nullable=False),
        sa.Column("total_records", sa.Integer()),
        sa.Column("coverage_state", sa.String(32), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_complete_at", sa.DateTime(timezone=True)),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("source_modified_at", sa.DateTime(timezone=True)),
        sa.Column("records_collected", sa.Integer(), nullable=False),
        sa.Column("records_created", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_unchanged", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(240)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "federal_opportunity_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("opportunity_id", sa.String(300), nullable=False),
        sa.Column("source_revision", sa.String(64), nullable=False),
        sa.Column("input_revision", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("projection", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "opportunity_id", "version", name="uq_federal_opportunity_version"
        ),
    )
    op.create_index(
        "ix_federal_opportunity_current",
        "federal_opportunity_assessments",
        ["opportunity_id", "is_current"],
    )


def downgrade():
    raise RuntimeError(
        "Retain federal opportunity collection coverage and assessment lineage; "
        "restore a compatible reviewed backup instead."
    )
