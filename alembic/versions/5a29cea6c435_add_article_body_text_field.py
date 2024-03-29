"""Add article body_text field

Revision ID: 5a29cea6c435
Revises: a55cb56957e2
Create Date: 2021-05-31 23:26:04.270642

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a29cea6c435'
down_revision = 'a55cb56957e2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('article', sa.Column('body_text', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('article', 'body_text')
    # ### end Alembic commands ###
