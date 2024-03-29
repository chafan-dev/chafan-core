"""Update invitation link model

Revision ID: 690f409863df
Revises: efd4a8bf854e
Create Date: 2021-02-22 22:35:39.623192

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '690f409863df'
down_revision = 'efd4a8bf854e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('invitationlink',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.CHAR(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expired_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('inviter_id', sa.Integer(), nullable=False),
    sa.Column('invited_to_site_id', sa.Integer(), nullable=True),
    sa.Column('remaining_quota', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['invited_to_site_id'], ['site.id'], ),
    sa.ForeignKeyConstraint(['inviter_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invitationlink_uuid'), 'invitationlink', ['uuid'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_invitationlink_uuid'), table_name='invitationlink')
    op.drop_table('invitationlink')
    # ### end Alembic commands ###
