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
    # Add log_path column
    op.add_column("training_runs", sa.Column("log_path", sa.String(), nullable=True))

    # Update status default from 'completed' to 'pending'
    op.alter_column(
        "training_runs",
        "status",
        server_default="'pending'",
    )


def downgrade() -> None:
    op.drop_column("training_runs", "log_path")
    op.alter_column(
        "training_runs",
        "status",
        server_default="'completed'",
    )
