"""Add user keywords

Revision ID: 91aa83eae955
Revises: 0f8b2edf3460
Create Date: 2021-09-07 23:44:46.665921

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91aa83eae955'
down_revision = '0f8b2edf3460'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('site', 'name',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.add_column('user', sa.Column('keywords', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'keywords')
    op.alter_column('site', 'name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###
