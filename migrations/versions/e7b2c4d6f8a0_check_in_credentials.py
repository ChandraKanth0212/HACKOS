"""Add secure participant check-in credential fields.

Revision ID: e7b2c4d6f8a0
Revises: d8a4b3c2e1f0
"""

from alembic import op
import sqlalchemy as sa


revision = "e7b2c4d6f8a0"
down_revision = "d8a4b3c2e1f0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("participants") as batch_op:
        batch_op.add_column(sa.Column("check_in_token_nonce", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("check_in_token_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("check_in_token_revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_unique_constraint(
            "uq_participants_check_in_token_nonce", ["check_in_token_nonce"]
        )


def downgrade():
    with op.batch_alter_table("participants") as batch_op:
        batch_op.drop_constraint("uq_participants_check_in_token_nonce", type_="unique")
        batch_op.drop_column("check_in_token_revoked_at")
        batch_op.drop_column("check_in_token_hash")
        batch_op.drop_column("check_in_token_nonce")
