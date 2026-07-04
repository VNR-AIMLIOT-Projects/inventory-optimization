"""add log_path and update status defaults

Revision ID: 002
Revises: 001
Create Date: 2026-03-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("training_runs") as batch_op:
        batch_op.add_column(sa.Column("log_path", sa.String(), nullable=True))
        batch_op.alter_column(
            "status",
            server_default="'pending'",
        )


def downgrade() -> None:
    with op.batch_alter_table("training_runs") as batch_op:
        batch_op.drop_column("log_path")
        batch_op.alter_column(
            "status",
            server_default="'completed'",
        )
