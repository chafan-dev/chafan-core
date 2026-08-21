"""Add token_version and bot_token_version

Revocation for stateless JWTs. Both columns are NOT NULL with a server default
of 0, and every token issued before this shipped carries no version claim --
which TokenPayload reads as 0. Those two zeroes have to agree, or deploying
this refuses every existing session at once.

ADD COLUMN with a non-volatile DEFAULT has not rewritten the table since
Postgres 11, so this is a catalog change rather than a table scan.

Revision ID: c8e21f7a9b34
Revises: b4d17c9e2f08
Create Date: 2026-08-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e21f7a9b34'
down_revision = 'b4d17c9e2f08'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user',
        sa.Column(
            'token_version', sa.Integer(), nullable=False, server_default='0'
        ),
    )
    op.add_column(
        'user',
        sa.Column(
            'bot_token_version', sa.Integer(), nullable=False, server_default='0'
        ),
    )


def downgrade():
    op.drop_column('user', 'bot_token_version')
    op.drop_column('user', 'token_version')
