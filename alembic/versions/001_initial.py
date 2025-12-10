"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('total_training_hours', sa.Float(), default=0.0),
        sa.Column('total_tokens_generated', sa.Integer(), default=0),
    )
    
    # Create datasets table
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gcs_path', sa.String(500), nullable=False),
        sa.Column('local_path', sa.String(500), nullable=True),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('dvc_hash', sa.String(64), nullable=True),
        sa.Column('num_files', sa.Integer(), default=0),
        sa.Column('total_size_bytes', sa.Integer(), default=0),
        sa.Column('num_samples', sa.Integer(), default=0),
        sa.Column('languages', sa.JSON(), nullable=True),
        sa.Column('is_processed', sa.Boolean(), default=False),
        sa.Column('processing_status', sa.String(50), default='pending'),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create training_jobs table
    op.create_table(
        'training_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('dataset_id', sa.String(36), sa.ForeignKey('datasets.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('pending', 'queued', 'running', 'completed', 'failed', 'cancelled', name='jobstatus'), default='pending'),
        sa.Column('progress', sa.Float(), default=0.0),
        sa.Column('current_step', sa.Integer(), default=0),
        sa.Column('total_steps', sa.Integer(), default=0),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('current_metrics', sa.JSON(), nullable=True),
        sa.Column('final_metrics', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('gpu_hours', sa.Float(), default=0.0),
        sa.Column('estimated_cost', sa.Float(), default=0.0),
        sa.Column('mlflow_run_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    
    # Create adapters table
    op.create_table(
        'adapters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('training_job_id', sa.String(36), sa.ForeignKey('training_jobs.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('base_model', sa.String(255), default='bigcode/starcoder2-3b'),
        sa.Column('gcs_path', sa.String(500), nullable=False),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('lora_config', sa.JSON(), nullable=True),
        sa.Column('is_deployed', sa.Boolean(), default=False),
        sa.Column('deployed_at', sa.DateTime(), nullable=True),
        sa.Column('inference_count', sa.Integer(), default=0),
        sa.Column('total_tokens_generated', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create feedback_logs table
    op.create_table(
        'feedback_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('adapter_id', sa.String(36), sa.ForeignKey('adapters.id'), nullable=False),
        sa.Column('prompt_hash', sa.String(64), nullable=False),
        sa.Column('response_length', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('feedback_type', sa.String(50), default='thumbs'),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('feedback_logs')
    op.drop_table('adapters')
    op.drop_table('training_jobs')
    op.drop_table('datasets')
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS jobstatus')
