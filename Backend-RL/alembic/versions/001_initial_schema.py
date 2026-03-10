"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("filepath", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("skus", sa.JSON(), server_default="[]"),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uploaded_file_id", sa.Integer(), sa.ForeignKey("uploaded_files.id"), nullable=True),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("season_type", sa.String(), nullable=False),
        sa.Column("episodes", sa.Integer(), nullable=False),
        sa.Column("holding_cost", sa.Float(), server_default="5.0"),
        sa.Column("stockout_penalty", sa.Float(), server_default="200.0"),
        sa.Column("max_order", sa.Integer(), nullable=True),
        sa.Column("action_step", sa.Integer(), nullable=True),
        sa.Column("best_reward", sa.Float(), nullable=True),
        sa.Column("final_avg_reward", sa.Float(), nullable=True),
        sa.Column("rewards", sa.JSON(), server_default="[]"),
        sa.Column("model_path", sa.String(), nullable=True),
        sa.Column("demand_params", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), server_default="'completed'"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("training_run_id", sa.Integer(), sa.ForeignKey("training_runs.id"), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("rl_reward", sa.Float(), nullable=False),
        sa.Column("oracle_reward", sa.Float(), nullable=False),
        sa.Column("rule_reward", sa.Float(), nullable=False),
        sa.Column("rl_vs_oracle_pct", sa.Float(), nullable=True),
        sa.Column("config", sa.JSON(), server_default="{}"),
        sa.Column("eval_graph_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("evaluation_results")
    op.drop_table("training_runs")
    op.drop_table("uploaded_files")
