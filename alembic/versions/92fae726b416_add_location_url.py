"""Add location_url

Revision ID: 92fae726b416
Revises: ce37e212bb64
Create Date: 2021-12-24 00:37:59.806346

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '92fae726b416'
down_revision = 'ce37e212bb64'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('feedback', sa.Column('location_url', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('feedback', 'location_url')
    # ### end Alembic commands ###