"""Drop verified_telegram_user_id

The Telegram bot integration this column served was never driven: every commit
touching endpoints/bot.py and services/bot.py is a refactor sweep, and no test
ever exercised it. The column is dropped with the code.

Revision ID: b4d17c9e2f08
Revises: 3c2f1a8b9d4e
Create Date: 2026-08-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4d17c9e2f08'
down_revision = '3c2f1a8b9d4e'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('user', 'verified_telegram_user_id')


def downgrade():
    op.add_column('user', sa.Column('verified_telegram_user_id', sa.String(), nullable=True))
