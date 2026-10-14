"""create faqs

Revision ID: f3a8d1c6b925
Revises: a4c91e7d3b68
Create Date: 2026-10-14 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f3a8d1c6b925"
down_revision: Union[str, None] = "a4c91e7d3b68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "faqs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_faqs_category"), "faqs", ["category"])


def downgrade() -> None:
    op.drop_index(op.f("ix_faqs_category"), table_name="faqs")
    op.drop_table("faqs")
