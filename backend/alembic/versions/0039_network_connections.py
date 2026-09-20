"""Add tenant-scoped imported professional network records."""

import sqlalchemy as sa
from alembic import op

revision = "0039_network_connections"
down_revision = "0038_federal_opportunity_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("network_import_batches",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("source_kind", sa.String(64), nullable=False), sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False), sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_person_id", sa.String(64)), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input_row_count", sa.Integer, nullable=False), sa.Column("imported_row_count", sa.Integer, nullable=False),
        sa.Column("resolved_row_count", sa.Integer, nullable=False), sa.Column("unresolved_row_count", sa.Integer, nullable=False),
        sa.Column("data_mode", sa.String(32), nullable=False),
        sa.CheckConstraint("data_mode = 'IMPORTED'", name="ck_network_batch_imported"),
        sa.UniqueConstraint("tenant_id", "source_kind", "file_sha256", name="uq_network_import_file"))
    op.create_table("network_people",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False), sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("profile_url", sa.Text), sa.Column("batch_id", sa.String(64), sa.ForeignKey("network_import_batches.id"), nullable=False),
        sa.CheckConstraint("kind IN ('internal', 'external')", name="ck_network_person_kind"))
    op.create_index("ix_network_people_tenant_kind", "network_people", ["tenant_id", "kind"])
    op.create_index("ix_network_people_batch", "network_people", ["batch_id"])
    op.create_table("network_affiliations",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("person_id", sa.String(64), sa.ForeignKey("network_people.id"), nullable=False),
        sa.Column("raw_company_string", sa.String(500), nullable=False), sa.Column("raw_title", sa.String(500)),
        sa.Column("account_id", sa.String(64), sa.ForeignKey("accounts.id")), sa.Column("resolution_method", sa.String(64), nullable=False),
        sa.Column("resolution_state", sa.String(32), nullable=False), sa.Column("role_family", sa.String(120), nullable=False),
        sa.Column("seniority_tier", sa.String(32), nullable=False), sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False), sa.Column("data_mode", sa.String(32), nullable=False),
        sa.Column("synthetic", sa.Boolean, nullable=False),
        sa.CheckConstraint("data_mode = 'IMPORTED' AND synthetic = false", name="ck_network_affiliation_truth"))
    op.create_index("ix_network_affiliations_account", "network_affiliations", ["tenant_id", "account_id"])
    op.create_index("ix_network_affiliations_person", "network_affiliations", ["tenant_id", "person_id"])
    op.create_table("network_ties",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("internal_person_id", sa.String(64), sa.ForeignKey("network_people.id"), nullable=False),
        sa.Column("external_person_id", sa.String(64), sa.ForeignKey("network_people.id"), nullable=False),
        sa.Column("connected_on", sa.DateTime(timezone=True)), sa.Column("batch_id", sa.String(64), sa.ForeignKey("network_import_batches.id"), nullable=False),
        sa.Column("tie_source", sa.String(64), nullable=False), sa.Column("evidence_state", sa.String(32), nullable=False),
        sa.Column("data_mode", sa.String(32), nullable=False), sa.Column("synthetic", sa.Boolean, nullable=False),
        sa.CheckConstraint("data_mode = 'IMPORTED' AND synthetic = false", name="ck_network_tie_truth"),
        sa.UniqueConstraint("tenant_id", "batch_id", "internal_person_id", "external_person_id", name="uq_network_tie"))
    op.create_index("ix_network_ties_internal", "network_ties", ["tenant_id", "internal_person_id"])
    op.create_index("ix_network_ties_external", "network_ties", ["tenant_id", "external_person_id"])
    op.create_table("network_unresolved_companies",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("network_import_batches.id"), nullable=False),
        sa.Column("company_fingerprint", sa.String(64), nullable=False), sa.Column("raw_company_string", sa.String(500), nullable=False),
        sa.Column("resolution_state", sa.String(32), nullable=False), sa.Column("resolution_method", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False), sa.Column("occurrence_count", sa.Integer, nullable=False),
        sa.UniqueConstraint("tenant_id", "batch_id", "company_fingerprint", name="uq_network_unresolved_company"))


def downgrade():
    raise RuntimeError("Retain imported network lineage; restore a reviewed compatible backup instead.")
