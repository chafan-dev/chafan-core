"""Add subject_user_uuid

Revision ID: 43be589a3aca
Revises: fcdd9de59683
Create Date: 2021-04-17 11:08:44.490933

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43be589a3aca'
down_revision = 'fcdd9de59683'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('feed', sa.Column('subject_user_uuid', sa.CHAR(length=20), nullable=True))
    op.create_foreign_key(None, 'feed', 'user', ['subject_user_uuid'], ['uuid'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'feed', type_='foreignkey')
    op.drop_column('feed', 'subject_user_uuid')
    # ### end Alembic commands ###
