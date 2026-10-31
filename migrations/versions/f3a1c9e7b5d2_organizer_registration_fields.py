"""Allow pre-event organizer accounts and store display names.

Revision ID: f3a1c9e7b5d2
Revises: e7b2c4d6f8a0
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a1c9e7b5d2"
down_revision = "e7b2c4d6f8a0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "event_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )
        batch_op.add_column(sa.Column("display_name", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("display_name")
        batch_op.alter_column(
            "event_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
