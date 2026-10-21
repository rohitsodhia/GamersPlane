"""create reports

Revision ID: a9d3f5b27c14
Revises: f3a8d1c6b925
Create Date: 2026-10-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a9d3f5b27c14"
down_revision: Union[str, None] = "f3a8d1c6b925"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_file", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_reporter_id"), "reports", ["reporter_id"])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])
    op.create_index(
        "uq_reports_open_per_reporter_target",
        "reports",
        ["reporter_id", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("uq_reports_open_per_reporter_target", table_name="reports")
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_index(op.f("ix_reports_reporter_id"), table_name="reports")
    op.drop_table("reports")
