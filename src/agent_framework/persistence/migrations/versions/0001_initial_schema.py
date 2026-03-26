"""初始数据库 schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(255), nullable=False, index=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "run_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(255), nullable=False, index=True),
        sa.Column("run_id", sa.String(255), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("input_summary", sa.Text, nullable=True),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("run_logs")
    op.drop_table("sessions")
