"""add strategy lab batch id

Revision ID: 20260608_0001
Revises: 20260521_0001
Create Date: 2026-06-08 22:52:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260608_0001"
down_revision: Union[str, Sequence[str], None] = "20260521_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("strategy_lab_batch_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_runs_strategy_lab_batch_id"), "runs", ["strategy_lab_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_runs_strategy_lab_batch_id"), table_name="runs")
    op.drop_column("runs", "strategy_lab_batch_id")
