"""Converge legacy work items into durable authorized Actions.

Revision ID: 0015_durable_authorized_actions
Revises: 0014_program_candidate_promotion_audit
"""

import sqlalchemy as sa

from alembic import op

revision = "0015_durable_authorized_actions"
down_revision = "0014_program_candidate_promotion_audit"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    account_foreign_keys = [
        item
        for item in inspector.get_foreign_keys("work_items")
        if item["constrained_columns"] == ["account_id"]
    ]
    if account_foreign_keys and op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            account_foreign_keys[0]["name"], "work_items", type_="foreignkey"
        )
    columns = _columns("work_items")
    additions = {
        "description": sa.Column("description", sa.Text()),
        "approval_status": sa.Column(
            "approval_status",
            sa.String(32),
            nullable=False,
            server_default="NOT_REQUIRED",
        ),
        "source_suggestion_id": sa.Column("source_suggestion_id", sa.String(160)),
        "created_by": sa.Column(
            "created_by", sa.String(128), nullable=False, server_default="migration"
        ),
        "updated_at": sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        "completed_at": sa.Column("completed_at", sa.DateTime(timezone=True)),
        "canceled_at": sa.Column("canceled_at", sa.DateTime(timezone=True)),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("work_items", column)
    op.execute(
        "UPDATE work_items SET status = CASE WHEN status = 'COMPLETED' THEN 'COMPLETED' WHEN status = 'DISMISSED' THEN 'CANCELED' WHEN status IN ('IN_REVIEW', 'ASSIGNED', 'APPROVED', 'FOLLOW_UP') THEN 'IN_PROGRESS' ELSE 'OPEN' END"
    )
    uniques = {
        tuple(item["column_names"])
        for item in sa.inspect(op.get_bind()).get_unique_constraints("work_items")
    }
    if ("source_suggestion_id",) not in uniques:
        op.create_unique_constraint(
            "uq_work_items_source_suggestion_id", "work_items", ["source_suggestion_id"]
        )
    audit_columns = _columns("work_audit_events")
    if "metadata" not in audit_columns:
        op.add_column(
            "work_audit_events",
            sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        )
    if not sa.inspect(op.get_bind()).has_table("action_suggestion_decisions"):
        op.create_table(
            "action_suggestion_decisions",
            sa.Column("suggestion_id", sa.String(160), primary_key=True),
            sa.Column("dismissed_by", sa.String(128), nullable=False),
            sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("action_suggestion_decisions"):
        op.drop_table("action_suggestion_decisions")
    uniques = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_unique_constraints("work_items")
    }
    if "uq_work_items_source_suggestion_id" in uniques:
        op.drop_constraint(
            "uq_work_items_source_suggestion_id", "work_items", type_="unique"
        )
    if "metadata" in _columns("work_audit_events"):
        op.drop_column("work_audit_events", "metadata")
    for name in (
        "canceled_at",
        "completed_at",
        "updated_at",
        "created_by",
        "source_suggestion_id",
        "approval_status",
        "description",
    ):
        if name in _columns("work_items"):
            op.drop_column("work_items", name)
    existing_foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("work_items")
    if op.get_bind().dialect.name == "postgresql" and not any(
        item["constrained_columns"] == ["account_id"] for item in existing_foreign_keys
    ):
        op.create_foreign_key(
            "work_items_account_id_fkey",
            "work_items",
            "accounts",
            ["account_id"],
            ["id"],
        )
