"""Join Actions and network/chat migrations without renaming applied revisions."""

revision = "0042_merge_actions_network_chat"
down_revision = ("0039_actions_pm_workspace", "0041_omni_conversations")
branch_labels = None
depends_on = None


def upgrade():
    # Both parent chains are additive and operate on separate feature tables.
    # Alembic applies the missing parent chain before reaching this common head.
    pass


def downgrade():
    # Splitting this merge changes version markers only; parent histories remain.
    pass
