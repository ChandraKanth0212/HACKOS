"""Constrain participant registration status.

Revision ID: d8a4b3c2e1f0
Revises: c7f1e2a4b9d0
"""
from alembic import op


revision = "d8a4b3c2e1f0"
down_revision = "c7f1e2a4b9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("participants") as batch_op:
        batch_op.create_check_constraint(
            "ck_participants_registration_status",
            "registration_status IN "
            "('pending', 'confirmed', 'cancelled', 'flagged_duplicate')",
        )


def downgrade():
    with op.batch_alter_table("participants") as batch_op:
        batch_op.drop_constraint(
            "ck_participants_registration_status", type_="check"
        )
