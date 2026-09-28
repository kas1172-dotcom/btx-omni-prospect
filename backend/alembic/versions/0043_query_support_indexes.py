"""Additive, idempotent query indexes.

Validate with EXPLAIN (ANALYZE, BUFFERS) on a copy of production data before
relying on these indexes for performance. Use CREATE INDEX CONCURRENTLY at scale.
"""

import sqlalchemy as sa
from alembic import op

revision = "0043_query_support_indexes"
down_revision = "0042_merge_actions_network_chat"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_monitor_observations_collection_run_id", "monitor_observations", ["collection_run_id"], None),
    ("ix_monitor_events_source_observation_id", "monitor_events", ["source_observation_id"], None),
    ("ix_monitor_events_resolved_publication_date", "monitor_events", ["publication_date"], "resolution_state = 'RESOLVED'"),
    ("ix_monitor_event_clusters_event_id", "monitor_event_clusters", ["event_id"], None),
    ("ix_work_audit_events_work_item_id", "work_audit_events", ["work_item_id"], None),
    ("ix_communication_audit_events_communication_id", "communication_audit_events", ["communication_id"], None),
)


def upgrade():
    for name, table, columns, predicate in _INDEXES:
        existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
        if name not in existing:
            options = {"postgresql_where": sa.text(predicate)} if predicate else {}
            op.create_index(name, table, columns, **options)


def downgrade():
    for name, table, _columns, _predicate in reversed(_INDEXES):
        existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
        if name in existing:
            op.drop_index(name, table_name=table)
