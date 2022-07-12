"""Add shard to timeline of my comment feature

Revision ID: 1541eb7cdb55
Revises: 820e2f9cfb02
Create Date: 2021-01-31 19:25:00.347776

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1541eb7cdb55'
down_revision = '820e2f9cfb02'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comment', sa.Column('shared_to_timeline', sa.Boolean(), server_default='false', nullable=False))
    op.alter_column('site', 'moderator_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('site', 'moderator_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_column('comment', 'shared_to_timeline')
    # ### end Alembic commands ###