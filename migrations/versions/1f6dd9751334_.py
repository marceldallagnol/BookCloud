"""empty message

Revision ID: 1f6dd9751334
Revises: 27526300ea23
Create Date: 2016-10-30 19:21:34.732975

"""

# revision identifiers, used by Alembic.
revision = '1f6dd9751334'
down_revision = '27526300ea23'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comment', sa.Column('posted_at', sa.DateTime(), nullable=True))
    op.add_column('thread', sa.Column('posted_at', sa.DateTime(), nullable=True))
    ### end Alembic commands ###

def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('thread', 'posted_at')
    op.drop_column('comment', 'posted_at')
    ### end Alembic commands ###