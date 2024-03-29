"""Payment model

Revision ID: 8211a967ea0a
Revises: 5e5dc2de75fe
Create Date: 2020-12-27 00:20:00.249339

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8211a967ea0a'
down_revision = '5e5dc2de75fe'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('site', sa.Column('create_question_coin_deduction', sa.Integer(), server_default='5', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('site', 'create_question_coin_deduction')
    # ### end Alembic commands ###
