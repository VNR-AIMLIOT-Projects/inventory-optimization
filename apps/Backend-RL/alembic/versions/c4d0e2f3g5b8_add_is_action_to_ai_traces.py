"""add_is_action_to_ai_traces

Revision ID: c4d0e2f3g5b8
Revises: b3c9d1e2f4a7
Create Date: 2026-07-02 12:00:00.000000

Adds the is_action boolean to the ai_traces table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d0e2f3g5b8'
down_revision: Union[str, None] = 'b3c9d1e2f4a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name == 'sqlite':
        op.execute("ALTER TABLE ai_traces ADD COLUMN is_action INTEGER DEFAULT 0;")
        return

    # Postgres
    op.execute("ALTER TABLE ai_traces ADD COLUMN is_action BOOLEAN NOT NULL DEFAULT FALSE;")


def downgrade() -> None:
    conn = op.get_bind()
    
    if conn.dialect.name == 'sqlite':
        pass
    else:
        op.execute("ALTER TABLE ai_traces DROP COLUMN is_action;")
