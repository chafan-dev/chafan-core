"""Add field for prerendered answer body

Revision ID: 4fab480583ba
Revises: 3e61d9fd232c
Create Date: 2021-03-16 00:33:04.878936

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4fab480583ba'
down_revision = '3e61d9fd232c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('answer', sa.Column('body_prerendered', sa.String(), nullable=True))
    op.add_column('answer', sa.Column('prerendered_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_column('answer', 'source_format')
    op.drop_column('answer', 'math_enabled')
    op.drop_column('article', 'source_format')
    op.drop_column('article', 'math_enabled')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('article', sa.Column('math_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.add_column('article', sa.Column('source_format', sa.VARCHAR(), server_default=sa.text("'markdown'::character varying"), autoincrement=False, nullable=False))
    op.add_column('answer', sa.Column('math_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.add_column('answer', sa.Column('source_format', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.drop_column('answer', 'prerendered_at')
    op.drop_column('answer', 'body_prerendered')
    # ### end Alembic commands ###
