"""Add upload table

One row per accepted image upload; the object store holds one object per sha256.

Revision ID: 3c2f1a8b9d4e
Revises: 7a670908f3fa
Create Date: 2026-08-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c2f1a8b9d4e'
down_revision = '7a670908f3fa'
branch_labels = None
depends_on = None

# Named, rather than the ``None`` autogenerate emits: an unnamed constraint
# leaves the downgrade with no name to drop.
FK_NAME = "upload_uploader_id_fkey"


def upgrade():
    op.create_table(
        'upload',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uploader_id', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('storage_bucket', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['uploader_id'], ['user.id'], name=FK_NAME),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_upload_id'), 'upload', ['id'], unique=False)
    op.create_index(op.f('ix_upload_uploader_id'), 'upload', ['uploader_id'], unique=False)
    op.create_index(op.f('ix_upload_sha256'), 'upload', ['sha256'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_upload_sha256'), table_name='upload')
    op.drop_index(op.f('ix_upload_uploader_id'), table_name='upload')
    op.drop_index(op.f('ix_upload_id'), table_name='upload')
    op.drop_constraint(FK_NAME, 'upload', type_='foreignkey')
    op.drop_table('upload')
