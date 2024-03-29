"""Add submission keywords field

Revision ID: 2d600f126b2a
Revises: b8d3e3432d39
Create Date: 2021-04-01 11:49:51.274291

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d600f126b2a'
down_revision = 'b8d3e3432d39'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('submission', sa.Column('keywords', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('submission', 'keywords')
    # ### end Alembic commands ###
