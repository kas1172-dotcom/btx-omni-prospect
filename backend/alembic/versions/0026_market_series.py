"""Add public market observations, immutable vintages and refresh receipts."""
import sqlalchemy as sa

from alembic import op
from btx_omni.persistence.market_series import (
    market_refresh_runs,
    market_series_current,
    market_series_vintages,
)

revision = '0026_market_series'
down_revision = '0025_work_feedback'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (market_series_vintages, market_series_current, market_refresh_runs):
        inspector = sa.inspect(bind)
        if inspector.has_table(table.name):
            columns = {c['name']: c for c in inspector.get_columns(table.name)}
            if set(columns) != set(table.c.keys()) or any(
                not isinstance(columns[c.name]['type'], type(c.type)) or columns[c.name]['nullable'] != c.nullable
                for c in table.c
            ):
                raise RuntimeError('Existing market table has an incompatible column contract.')
            if inspector.get_pk_constraint(table.name)['constrained_columns'] != [c.name for c in table.primary_key]:
                raise RuntimeError('Existing market table lacks its canonical primary key.')
            if table is market_series_current and not any(
                fk['constrained_columns'] == ['vintage_id'] and fk['referred_table'] == market_series_vintages.name
                and fk['referred_columns'] == ['id'] for fk in inspector.get_foreign_keys(table.name)
            ):
                raise RuntimeError('Existing market pointer lacks its vintage foreign key.')
        else:
            table.create(bind)


def downgrade():
    raise RuntimeError('Preserve original market vintages; use a compatible code rollback or reviewed backup restore.')
