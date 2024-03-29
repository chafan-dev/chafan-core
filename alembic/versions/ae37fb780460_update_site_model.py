"""Update site model

Revision ID: ae37fb780460
Revises: ebc55177cad6
Create Date: 2021-01-03 16:59:06.113963

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae37fb780460'
down_revision = 'ebc55177cad6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_site_subdomain'), 'site', ['subdomain'], unique=True)
    op.drop_constraint('site_subdomain_key', 'site', type_='unique')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint('site_subdomain_key', 'site', ['subdomain'])
    op.drop_index(op.f('ix_site_subdomain'), table_name='site')
    # ### end Alembic commands ###
