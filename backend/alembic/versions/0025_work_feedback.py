"""Add immutable private feedback without rewriting legacy work or dismissals."""
import sqlalchemy as sa

from alembic import op

revision = '0025_work_feedback'
down_revision = '0024_monitor_funnel'
branch_labels = None
depends_on = None

# Freeze this revision's table contract. Importing the live ORM table would
# retroactively include columns belonging to later migrations on fresh installs.
work_suggestion_feedback = sa.Table(
    'work_suggestion_feedback', sa.MetaData(),
    sa.Column('id', sa.String(36), primary_key=True),
    sa.Column('user_id', sa.String(128), nullable=False),
    sa.Column('suggestion_id', sa.String(160), nullable=False),
    sa.Column('account_id', sa.String(64), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(32), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('snooze_until', sa.DateTime(timezone=True)),
    sa.Column('previous_feedback_id', sa.String(36)),
    sa.Column('idempotency_key', sa.String(64), nullable=False),
    sa.Column('request_hash', sa.String(64), nullable=False),
    sa.UniqueConstraint('user_id', 'idempotency_key', name='uq_work_feedback_user_request'),
    sa.UniqueConstraint('user_id', 'suggestion_id', 'version', name='uq_work_feedback_user_version'),
)
sa.Index('ix_work_feedback_user_suggestion', work_suggestion_feedback.c.user_id, work_suggestion_feedback.c.suggestion_id)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(work_suggestion_feedback.name):
        columns = {c['name']: c for c in inspector.get_columns(work_suggestion_feedback.name)}
        if set(columns) != set(work_suggestion_feedback.c.keys()) or any(
            not isinstance(columns[c.name]['type'], type(c.type)) or columns[c.name]['nullable'] != c.nullable
            for c in work_suggestion_feedback.c
        ):
            raise RuntimeError('Existing feedback table has an incompatible column contract.')
        uniques = {tuple(c['column_names']) for c in inspector.get_unique_constraints(work_suggestion_feedback.name)}
        if not {('user_id', 'idempotency_key'), ('user_id', 'suggestion_id', 'version')} <= uniques:
            raise RuntimeError('Existing feedback table lacks isolation/replay constraints.')
        if inspector.get_pk_constraint(work_suggestion_feedback.name)['constrained_columns'] != ['id']:
            raise RuntimeError('Existing feedback table lacks immutable receipt identity.')
        return
    work_suggestion_feedback.create(bind)


def downgrade():
    # Undo is an appended user event, not permission to erase feedback history.
    raise RuntimeError('Feedback history must be preserved; use a compatible code rollback or a reviewed backup restoration.')
