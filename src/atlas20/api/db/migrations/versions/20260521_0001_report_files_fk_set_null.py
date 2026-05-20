"""report_files run_id set null on run delete

Revision ID: 20260521_0001
Revises: 20260520_0001
Create Date: 2026-05-21 03:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0001"
down_revision: Union[str, Sequence[str], None] = "20260520_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_report_files_run_id_runs"
NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _current_fk_name() -> str | None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("report_files"):
        if fk["constrained_columns"] == ["run_id"] and fk["referred_table"] == "runs":
            return fk["name"]
    return None


def _replace_fk(ondelete: str | None) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("report_files", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.drop_constraint(FK_NAME, type_="foreignkey")
            batch_op.create_foreign_key(FK_NAME, "runs", ["run_id"], ["run_id"], ondelete=ondelete)
        return

    op.drop_constraint(_current_fk_name() or FK_NAME, "report_files", type_="foreignkey")
    op.create_foreign_key(FK_NAME, "report_files", "runs", ["run_id"], ["run_id"], ondelete=ondelete)


def upgrade() -> None:
    _replace_fk(ondelete="SET NULL")


def downgrade() -> None:
    _replace_fk(ondelete=None)
