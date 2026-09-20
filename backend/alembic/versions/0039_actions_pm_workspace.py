"""Personal tasks, recoverable cancellation and one-level audited subtasks."""

import json

import sqlalchemy as sa

from alembic import op

revision = "0039_actions_pm_workspace"
down_revision = "0038_federal_opportunity_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column['name']: column for column in inspector.get_columns('work_items')}
    with op.batch_alter_table("work_items") as batch:
        if not columns['account_id']['nullable']:
            batch.alter_column("account_id", existing_type=sa.String(64), nullable=True)
        for name, datatype in [('previous_status', sa.String(32)), ('approval_requested_by', sa.String(128)), ('approval_comment', sa.Text())]:
            if name not in columns:
                batch.add_column(sa.Column(name, datatype))
    if not inspector.has_table('action_subtasks'):
        op.create_table("action_subtasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("parent_id", sa.String(64), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("due_date", sa.String(16)),
        sa.Column("owner_id", sa.String(128)),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.create_index("ix_action_subtasks_parent_id", "action_subtasks", ["parent_id"])
    # Recover legacy cancellation from recorded facts only. No guessed previous state.
    connection = op.get_bind()
    events = connection.execute(sa.text("SELECT work_item_id, metadata FROM work_audit_events WHERE event = 'STATUS_CHANGED' ORDER BY id")).all()
    for action_id, raw in events:
        event = json.loads(raw or "{}")
        if event.get("after") == "CANCELED" and event.get("before") in {"OPEN", "IN_PROGRESS"}:
            connection.execute(sa.text("UPDATE work_items SET previous_status = :previous WHERE id = :id AND status = 'CANCELED'"),
                               {"previous": event["before"], "id": action_id})


def downgrade():
    raise RuntimeError("Retain subtask and approval history; use compatible rollback or reviewed restore.")
