"""Clean POC SQLAlchemy schema; domain objects remain framework-free."""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)

metadata = MetaData()
accounts = Table("accounts", metadata, Column("id", String(64), primary_key=True), Column("name", String(300), nullable=False), Column("relationship", String(32), nullable=False), Column("domain", String(300)))
facilities = Table("facilities", metadata, Column("id", String(64), primary_key=True), Column("account_id", ForeignKey("accounts.id"), nullable=False), Column("city", String(120), nullable=False), Column("region", String(64), nullable=False), Column("latitude", String(32), nullable=False), Column("longitude", String(32), nullable=False))
external_ranks = Table("external_industry_ranks", metadata, Column("account_id", ForeignKey("accounts.id"), primary_key=True), Column("industry", String(100), primary_key=True), Column("rank", Integer, nullable=False), Column("source", String(300), nullable=False))
identity_mappings = Table("identity_mappings", metadata, Column("source_key", String(300), primary_key=True), Column("account_id", ForeignKey("accounts.id"), nullable=False))
score_configurations = Table("score_configurations", metadata, Column("id", String(64), primary_key=True), Column("version", String(80), nullable=False), Column("hypothesis", Boolean, nullable=False), Column("interpretation_note", Text, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False))
score_assessments = Table("score_assessments", metadata, Column("id", String(64), primary_key=True), Column("account_id", ForeignKey("accounts.id"), nullable=False), Column("configuration_id", ForeignKey("score_configurations.id"), nullable=False), Column("status", String(32), nullable=False), Column("score", Numeric(5, 2)), Column("coverage", Numeric(5, 4), nullable=False), Column("evidence_ids", Text, nullable=False), Column("missing_fields", Text, nullable=False), Column("calculated_at", DateTime(timezone=True), nullable=False))
commercial_alerts = Table("commercial_alerts", metadata, Column("id", String(160), primary_key=True), Column("type", String(64), nullable=False), Column("account_id", ForeignKey("accounts.id"), nullable=False), Column("business_unit", String(100)), Column("severity", String(16), nullable=False), Column("trigger_reason", Text, nullable=False), Column("actual_value", Text, nullable=False), Column("threshold", Text, nullable=False), Column("evidence_ids", Text, nullable=False), Column("observed_at", DateTime(timezone=True), nullable=False), Column("recommended_action", Text, nullable=False), Column("owner_id", String(128)), Column("status", String(32), nullable=False), Column("synthetic", Boolean, nullable=False), Column("provenance_state", String(32), nullable=False))
intelligence_signals = Table("intelligence_signals", metadata, Column("id", String(64), primary_key=True), Column("type", String(64), nullable=False), Column("account_id", ForeignKey("accounts.id")), Column("program_name", String(300)), Column("source_url", Text, nullable=False), Column("evidence_state", String(32), nullable=False), Column("evidence_ids", Text, nullable=False), Column("occurred_at", DateTime(timezone=True), nullable=False))
commercial_matches = Table("commercial_matches", metadata, Column("component_id", String(64), primary_key=True), Column("quote_id", String(64), primary_key=True), Column("account_id", ForeignKey("accounts.id")), Column("method", String(32), nullable=False), Column("review_state", String(32), nullable=False), Column("evidence_state", String(32), nullable=False), Column("evidence_ids", Text, nullable=False), Column("business_unit", String(100)))
