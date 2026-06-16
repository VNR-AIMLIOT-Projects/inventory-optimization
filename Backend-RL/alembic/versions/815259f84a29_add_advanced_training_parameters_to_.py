"""Add advanced training parameters to TrainingRun

Revision ID: 815259f84a29
Revises: 002
Create Date: 2026-06-16 00:14:02.388765
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '815259f84a29'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    tables = inspector.get_table_names()

    if 'deployment_sessions' not in tables:
        op.create_table('deployment_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(), nullable=False),
        sa.Column('start_day', sa.Integer(), nullable=True),
        sa.Column('total_days', sa.Integer(), nullable=False),
        sa.Column('overrides', sa.JSON(), nullable=True),
        sa.Column('initial_inventory', sa.Integer(), nullable=False),
        sa.Column('max_order', sa.Integer(), nullable=False),
        sa.Column('action_step', sa.Integer(), nullable=False),
        sa.Column('holding_cost', sa.Float(), nullable=True),
        sa.Column('stockout_penalty', sa.Float(), nullable=True),
        sa.Column('final_rl_reward', sa.Float(), nullable=True),
        sa.Column('final_human_reward', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['training_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    # Check evaluation_results indexes
    if 'evaluation_results' in tables:
        eval_indexes = [idx['name'] for idx in inspector.get_indexes('evaluation_results')]
        if 'ix_evaluation_results_id' not in eval_indexes:
            op.create_index(op.f('ix_evaluation_results_id'), 'evaluation_results', ['id'], unique=False)
        
    # Check training_runs columns and indexes
    if 'training_runs' in tables:
        train_columns = [col['name'] for col in inspector.get_columns('training_runs')]
        if 'gamma' not in train_columns:
            op.add_column('training_runs', sa.Column('gamma', sa.Float(), nullable=True))
        if 'learning_rate' not in train_columns:
            op.add_column('training_runs', sa.Column('learning_rate', sa.Float(), nullable=True))
        if 'sweep_id' not in train_columns:
            op.add_column('training_runs', sa.Column('sweep_id', sa.String(), nullable=True))
            
        train_indexes = [idx['name'] for idx in inspector.get_indexes('training_runs')]
        if 'ix_training_runs_id' not in train_indexes:
            op.create_index(op.f('ix_training_runs_id'), 'training_runs', ['id'], unique=False)
            
    # Check uploaded_files indexes
    if 'uploaded_files' in tables:
        upload_indexes = [idx['name'] for idx in inspector.get_indexes('uploaded_files')]
        if 'ix_uploaded_files_id' not in upload_indexes:
            op.create_index(op.f('ix_uploaded_files_id'), 'uploaded_files', ['id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    tables = inspector.get_table_names()
    
    if 'uploaded_files' in tables:
        upload_indexes = [idx['name'] for idx in inspector.get_indexes('uploaded_files')]
        if 'ix_uploaded_files_id' in upload_indexes:
            op.drop_index(op.f('ix_uploaded_files_id'), table_name='uploaded_files')
            
    if 'training_runs' in tables:
        train_indexes = [idx['name'] for idx in inspector.get_indexes('training_runs')]
        if 'ix_training_runs_id' in train_indexes:
            op.drop_index(op.f('ix_training_runs_id'), table_name='training_runs')
            
        train_columns = [col['name'] for col in inspector.get_columns('training_runs')]
        if 'sweep_id' in train_columns:
            op.drop_column('training_runs', 'sweep_id')
        if 'learning_rate' in train_columns:
            op.drop_column('training_runs', 'learning_rate')
        if 'gamma' in train_columns:
            op.drop_column('training_runs', 'gamma')
            
    if 'evaluation_results' in tables:
        eval_indexes = [idx['name'] for idx in inspector.get_indexes('evaluation_results')]
        if 'ix_evaluation_results_id' in eval_indexes:
            op.drop_index(op.f('ix_evaluation_results_id'), table_name='evaluation_results')
            
    if 'deployment_sessions' in tables:
        op.drop_table('deployment_sessions')
