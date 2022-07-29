"""Add derived fields

Revision ID: 6162e247214e
Revises: 584772b747a3
Create Date: 2022-07-28 22:01:05.762211

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6162e247214e'
down_revision = '584772b747a3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('interesting_question_ids', sa.JSON(), nullable=True))
    op.add_column('user', sa.Column('interesting_question_ids_updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('user', sa.Column('interesting_user_ids', sa.JSON(), nullable=True))
    op.add_column('user', sa.Column('interesting_user_ids_updated_at', sa.DateTime(timezone=True), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'interesting_user_ids_updated_at')
    op.drop_column('user', 'interesting_user_ids')
    op.drop_column('user', 'interesting_question_ids_updated_at')
    op.drop_column('user', 'interesting_question_ids')
    # ### end Alembic commands ###
