"""Missing commercial lifecycle owners alongside the existing canonical tables."""
from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text

from btx_omni.persistence.models import (
    commercial_quotes,
    component_classes,
    crm_activities,
    crm_deals,
    metadata,
    monthly_commercial_history,
    orders,
    programs,
)

# Existing owners gain a lossless source field for attributes not represented by
# their indexed projection. This is not an additional account-history database.
SOURCE_PAYLOAD_TABLES = (programs, component_classes, monthly_commercial_history)
for table in SOURCE_PAYLOAD_TABLES:
    if "source_payload" not in table.c:
        table.append_column(Column("source_payload", Text))


def _records(name: str) -> Table:
    return Table(
        name, metadata,
        Column("id", String(220), primary_key=True),
        Column("account_id", ForeignKey("accounts.id"), nullable=False, index=True),
        Column("payload", Text, nullable=False),
        Column("source_system", String(120), nullable=False),
        Column("source_record_id", String(220), nullable=False),
        Column("source_version", String(64), nullable=False),
    )


commercial_account_profiles = _records("commercial_account_profiles")
LIFECYCLE_TABLES = {
    name: _records("commercial_" + name)
    for name in (
        "rfqs", "quote_revisions", "quote_lines", "agreements", "order_lines",
        "cancellations", "shipments", "acceptances", "revenue_events", "invoices",
        "payments", "service_events", "role_targets", "supply_relationships",
        "contacts", "actions", "fulfillment_plans",
    )
}
COLLECTION_TABLES = {
    **LIFECYCLE_TABLES,
    "programs": programs,
    "components": component_classes,
    "quotes": commercial_quotes,
    "orders": orders,
    "interactions": crm_activities,
    "opportunities": crm_deals,
    "monthly_commercial_history": monthly_commercial_history,
}

commercial_import_ownership = Table(
    "commercial_import_ownership", metadata,
    Column("table_name", String(100), primary_key=True),
    Column("record_id", String(220), primary_key=True),
    Column("package_key", String(120), nullable=False),
    Column("source_hash", String(64), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
commercial_import_runs = Table(
    "commercial_import_runs", metadata,
    Column("id", String(64), primary_key=True),
    Column("package_key", String(120), nullable=False),
    Column("manifest_hash", String(64), nullable=False),
    Column("as_of", String(10), nullable=False),
    Column("report", Text, nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
)
