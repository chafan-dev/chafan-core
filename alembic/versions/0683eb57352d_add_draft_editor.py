"""Add draft_editor

Revision ID: 0683eb57352d
Revises: 017a2ab5d597
Create Date: 2021-04-24 16:01:51.364264

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0683eb57352d'
down_revision = '017a2ab5d597'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('answer', sa.Column('draft_editor', sa.String(), server_default='wysiwyg', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('answer', 'draft_editor')
    # ### end Alembic commands ###
