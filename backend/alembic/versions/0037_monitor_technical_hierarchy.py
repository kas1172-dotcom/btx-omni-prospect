"""Version account-scoped Monitor technical decomposition projections."""

from __future__ import annotations

import hashlib

import sqlalchemy as sa

from alembic import op

revision = "0037_monitor_technical_hierarchy"
down_revision = "0036_monitor_business_briefings"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    old = sa.Table("monitor_technical_decompositions", metadata, autoload_with=bind)
    rows = [dict(row) for row in bind.execute(sa.select(old)).mappings()]
    replacement = op.create_table(
        "monitor_technical_decompositions_v2",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("context_key", sa.String(300), nullable=False),
        sa.Column("event_id", sa.String(160), nullable=False),
        sa.Column("account_id", sa.String(100)),
        sa.Column("source_revision", sa.String(64)),
        sa.Column("governed_content_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("projection", sa.Text()),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(120)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "context_key", "version", name="uq_monitor_technical_context_version"
        ),
    )
    for row in rows:
        context_key = f"{row['event_id']}|*"
        bind.execute(
            replacement.insert().values(
                id=hashlib.sha256(
                    f"{context_key}|1|{row['governed_content_hash']}".encode()
                ).hexdigest(),
                context_key=context_key,
                event_id=row["event_id"],
                account_id=None,
                source_revision=None,
                governed_content_hash=row["governed_content_hash"],
                version=1,
                is_current=True,
                projection=row.get("projection"),
                provider=row.get("provider"),
                model=row.get("model"),
                status=row["status"],
                attempt_count=row["attempt_count"],
                next_retry_at=row.get("next_retry_at"),
                processed_at=row["processed_at"],
            )
        )
    op.drop_table("monitor_technical_decompositions")
    op.rename_table(
        "monitor_technical_decompositions_v2", "monitor_technical_decompositions"
    )
    op.create_index(
        "ix_monitor_technical_current",
        "monitor_technical_decompositions",
        ["context_key", "is_current"],
    )


def downgrade():
    raise RuntimeError(
        "Retain versioned technical evidence lineage; restore a compatible reviewed backup instead."
    )
