"""Add organizer event management fields.

Revision ID: c7f1e2a4b9d0
Revises: a0ecac3d4ebb
"""
from alembic import op
import sqlalchemy as sa


revision = "c7f1e2a4b9d0"
down_revision = "a0ecac3d4ebb"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("venue", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("registration_starts_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("registration_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("capacity", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.Text(), nullable=False, server_default="draft"))
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        batch_op.create_check_constraint(
            "ck_events_capacity_positive", "capacity IS NULL OR capacity > 0"
        )
        batch_op.create_check_constraint(
            "ck_events_status_valid",
            "status IN ('draft', 'active', 'completed', 'cancelled')",
        )
        batch_op.create_foreign_key(
            "fk_events_owner_user_id_users", "users", ["owner_user_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("fk_events_owner_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("ck_events_status_valid", type_="check")
        batch_op.drop_constraint("ck_events_capacity_positive", type_="check")
        batch_op.drop_column("owner_user_id")
        batch_op.drop_column("status")
        batch_op.drop_column("capacity")
        batch_op.drop_column("registration_ends_at")
        batch_op.drop_column("registration_starts_at")
        batch_op.drop_column("venue")
        batch_op.drop_column("description")
