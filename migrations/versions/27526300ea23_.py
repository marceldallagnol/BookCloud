"""empty message

Revision ID: 27526300ea23
Revises: 7d18e1840349
Create Date: 2016-10-30 17:58:01.670411

"""

# revision identifiers, used by Alembic.
revision = '27526300ea23'
down_revision = '7d18e1840349'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('like')
    op.alter_column('likes', 'comment_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)
    op.alter_column('likes', 'owner_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('likes', 'owner_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=False)
    op.alter_column('likes', 'comment_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=False)
    op.create_table('like',
    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
    sa.Column('comment_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('owner_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['comment_id'], [u'comment.id'], name=u'like_ibfk_1'),
    sa.ForeignKeyConstraint(['owner_id'], [u'user.id'], name=u'like_ibfk_2'),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset=u'latin1',
    mysql_engine=u'InnoDB'
    )
    ### end Alembic commands ###