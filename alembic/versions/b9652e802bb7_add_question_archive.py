"""Add question archive

Revision ID: b9652e802bb7
Revises: 8b1e740e7911
Create Date: 2021-01-22 14:17:12.973108

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9652e802bb7'
down_revision = '8b1e740e7911'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('questionarchive',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_questionarchive_id'), 'questionarchive', ['id'], unique=False)
    op.create_index(op.f('ix_questionarchive_question_id'), 'questionarchive', ['question_id'], unique=False)
    op.create_table('question_archive_topics',
    sa.Column('question_archive_id', sa.Integer(), nullable=True),
    sa.Column('topic_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['question_archive_id'], ['questionarchive.id'], ),
    sa.ForeignKeyConstraint(['topic_id'], ['topic.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('question_archive_topics')
    op.drop_index(op.f('ix_questionarchive_question_id'), table_name='questionarchive')
    op.drop_index(op.f('ix_questionarchive_id'), table_name='questionarchive')
    op.drop_table('questionarchive')
    # ### end Alembic commands ###