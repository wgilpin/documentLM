"""add_source_indexing_fields

Revision ID: 3899adfca211
Revises: e9a1c3f5b2d8
Create Date: 2026-03-15 13:55:17.854023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3899adfca211'
down_revision: Union[str, Sequence[str], None] = 'e9a1c3f5b2d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


indexingstatus = sa.Enum('pending', 'processing', 'completed', 'failed', name='indexingstatus')


def upgrade() -> None:
    """Upgrade schema."""
    indexingstatus.create(op.get_bind(), checkfirst=True)
    op.drop_index(op.f('ix_chat_messages_document_id_created_at'), table_name='chat_messages')
    op.add_column('sources', sa.Column(
        'indexing_status',
        indexingstatus,
        nullable=False,
        server_default='pending',
    ))
    op.add_column('sources', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sources', 'error_message')
    op.drop_column('sources', 'indexing_status')
    indexingstatus.drop(op.get_bind(), checkfirst=True)
    op.create_index(op.f('ix_chat_messages_document_id_created_at'), 'chat_messages', ['document_id', 'created_at'], unique=False)
