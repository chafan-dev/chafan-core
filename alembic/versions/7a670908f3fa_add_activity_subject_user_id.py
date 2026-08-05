"""Add activity.subject_user_id

Step 1 of docs/proposals/2026-08-04-activity-feed-reassignment.md: give
Activity a subject column so subject timelines can be answered from the event
log instead of the delivery table. Nothing reads or writes it yet; steps 2 and
3 populate it.

Nullable on purpose. Every verb that writes an Activity today carries a
subject, but the deploy is two-phase (rows exist before step 2 fills them) and
historical rows whose payload will not parse must be allowed to stay null
rather than block the migration.

Revision ID: 7a670908f3fa
Revises: dd8d1f4a6434
Create Date: 2026-08-05 15:17:19.960392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a670908f3fa'
down_revision = 'dd8d1f4a6434'
branch_labels = None
depends_on = None

# Named, rather than the `None` autogenerate emits and most migrations here
# keep. An unnamed constraint leaves the downgrade with no name to drop -- the
# same defect that makes `alembic downgrade base` fail on the old `channel`
# migration (see .github/workflows/migrations.yml). The value below is what
# Postgres would have chosen anyway.
FK_NAME = "activity_subject_user_id_fkey"


def upgrade():
    op.add_column('activity', sa.Column('subject_user_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_activity_subject_user_id'), 'activity', ['subject_user_id'], unique=False)
    op.create_foreign_key(FK_NAME, 'activity', 'user', ['subject_user_id'], ['id'])


def downgrade():
    op.drop_constraint(FK_NAME, 'activity', type_='foreignkey')
    op.drop_index(op.f('ix_activity_subject_user_id'), table_name='activity')
    op.drop_column('activity', 'subject_user_id')
