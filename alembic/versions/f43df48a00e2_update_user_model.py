"""Update user model

Revision ID: f43df48a00e2
Revises: 690f409863df
Create Date: 2021-02-27 12:48:54.318762

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f43df48a00e2'
down_revision = '690f409863df'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('secondary_emails', sa.JSON(), server_default='[]', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user', 'secondary_emails')
    # ### end Alembic commands ###
