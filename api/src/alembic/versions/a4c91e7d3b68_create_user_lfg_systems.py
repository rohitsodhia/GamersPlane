"""create user lfg systems

Revision ID: a4c91e7d3b68
Revises: e7b3d94a1c52
Create Date: 2026-10-10 16:20:41.552310

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a4c91e7d3b68"
down_revision: Union[str, None] = "e7b3d94a1c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_lfg_systems",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("system_id", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.PrimaryKeyConstraint("user_id", "system_id"),
    )
    op.create_index(
        op.f("ix_user_lfg_systems_system_id"), "user_lfg_systems", ["system_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_lfg_systems_system_id"), table_name="user_lfg_systems")
    op.drop_table("user_lfg_systems")
