"""add catalog, commercial, relationship, and CRM source-shaped tables

Revision ID: 0008_commercial_and_edges
Revises: 0007_usaspending_relevance_state
"""
from alembic import op
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

revision = "0008_commercial_and_edges"
down_revision = "0007_usaspending_relevance_state"
branch_labels = None
depends_on = None


def _truth() -> list[Column]:
    return [Column("source_system", String(120), nullable=False), Column("source_record_id", String(160), nullable=False), Column("evidence_state", String(32), nullable=False), Column("data_mode", String(32), nullable=False), Column("synthetic", Boolean, nullable=False)]


def upgrade() -> None:
    op.create_table("programs", Column("id", String(100), primary_key=True), Column("account_id", String(64), ForeignKey("accounts.id")), Column("name", String(300), nullable=False), Column("system", String(120)), *_truth())
    op.create_table("component_classes", Column("id", String(100), primary_key=True), Column("program_id", String(100), ForeignKey("programs.id")), Column("name", String(300), nullable=False), Column("industry", String(100)), Column("business_unit_ids", Text, nullable=False), *_truth())
    op.create_table("bu_capabilities", Column("id", String(120), primary_key=True), Column("business_unit_id", String(100), nullable=False), Column("name", String(300), nullable=False), Column("payload", Text, nullable=False), *_truth())
    op.create_table("btx_facilities", Column("id", String(100), primary_key=True), Column("business_unit_id", String(100)), Column("name", String(300), nullable=False), Column("city", String(120)), Column("region", String(120)), Column("latitude", String(32)), Column("longitude", String(32)), *_truth())
    op.create_table("commercial_contexts", Column("id", String(180), primary_key=True), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("business_unit_id", String(100), nullable=False), Column("currency", String(12), nullable=False), Column("ttm_revenue_minor", Integer), Column("ttm_bookings_minor", Integer), Column("payload", Text, nullable=False), *_truth())
    op.create_table("monthly_commercial_history", Column("id", String(220), primary_key=True), Column("commercial_context_id", String(180), ForeignKey("commercial_contexts.id"), nullable=False), Column("month", String(10), nullable=False), Column("revenue_minor", Integer), Column("bookings_minor", Integer), *_truth())
    op.create_table("paperless_accounts", Column("id", String(120), primary_key=True), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("name", String(300), nullable=False), *_truth())
    op.create_table("commercial_quotes", Column("id", String(120), primary_key=True), Column("paperless_account_id", String(120), ForeignKey("paperless_accounts.id")), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("business_unit_id", String(100), nullable=False), Column("program_id", String(100), ForeignKey("programs.id")), Column("status", String(32), nullable=False), Column("quoted_at", String(10), nullable=False), Column("value_minor", Integer), Column("currency", String(12), nullable=False), Column("payload", Text, nullable=False), *_truth())
    op.create_table("orders", Column("id", String(120), primary_key=True), Column("quote_id", String(120), ForeignKey("commercial_quotes.id")), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("business_unit_id", String(100), nullable=False), Column("component_class_id", String(100), ForeignKey("component_classes.id"), nullable=False), Column("program_id", String(100), ForeignKey("programs.id"), nullable=False), Column("status", String(32), nullable=False), Column("promised_date", String(10)), Column("actual_ship_date", String(10)), Column("amount_minor", Integer, nullable=False), Column("payload", Text, nullable=False), *_truth())
    op.create_table("account_relationship_edges", Column("id", String(120), primary_key=True), Column("from_account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("to_account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("program_id", String(100), ForeignKey("programs.id")), Column("edge_type", String(64), nullable=False), Column("payload", Text, nullable=False), *_truth())
    op.create_table("crm_companies", Column("id", String(120), primary_key=True), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("owner_id", String(120)), Column("payload", Text, nullable=False), *_truth())
    op.create_table("crm_contacts", Column("id", String(120), primary_key=True), Column("company_id", String(120), ForeignKey("crm_companies.id"), nullable=False), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("role_family", String(120), nullable=False), Column("payload", Text, nullable=False), *_truth())
    op.create_table("crm_deals", Column("id", String(120), primary_key=True), Column("company_id", String(120), ForeignKey("crm_companies.id"), nullable=False), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("program_id", String(100), ForeignKey("programs.id")), Column("business_unit_id", String(100)), Column("payload", Text, nullable=False), *_truth())
    op.create_table("crm_activities", Column("id", String(120), primary_key=True), Column("company_id", String(120), ForeignKey("crm_companies.id"), nullable=False), Column("account_id", String(64), ForeignKey("accounts.id"), nullable=False), Column("occurred_at", DateTime(timezone=True), nullable=False), Column("payload", Text, nullable=False), *_truth())


def downgrade() -> None:
    for name in ("crm_activities", "crm_deals", "crm_contacts", "crm_companies", "account_relationship_edges", "orders", "commercial_quotes", "paperless_accounts", "monthly_commercial_history", "commercial_contexts", "btx_facilities", "bu_capabilities", "component_classes", "programs"):
        op.drop_table(name)
