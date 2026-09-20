"""Private conversations and feedback, separate from business data and memory."""
import sqlalchemy as sa

from alembic import op

revision = '0041_omni_conversations'
down_revision = '0040_network_visibility'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('omni_conversations',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('owner_key', sa.String(64), nullable=False),
        sa.Column('title', sa.String(80), nullable=False), sa.Column('turns', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_omni_conversations_owner_updated', 'omni_conversations', ['owner_key', 'updated_at'])
    op.create_table('omni_chat_feedback',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('conversation_id', sa.String(36), nullable=False),
        sa.Column('owner_key', sa.String(64), nullable=False), sa.Column('run_id', sa.String(36), nullable=False),
        sa.Column('rating', sa.String(4), nullable=False), sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('omni_chat_feedback')
    op.drop_table('omni_conversations')
