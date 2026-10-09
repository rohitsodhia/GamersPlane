"""create post rolls and post draws

Revision ID: c4e9a1f27b3d
Revises: b1da12dcebde
Create Date: 2026-10-09 15:12:41.118302

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4e9a1f27b3d"
down_revision: Union[str, None] = "b1da12dcebde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_rolls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("input", sa.String(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("hide_reason", sa.Boolean(), nullable=False),
        sa.Column("hide_dice", sa.Boolean(), nullable=False),
        sa.Column("hide_result", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_rolls_post_id"), "post_rolls", ["post_id"])
    op.create_table(
        "post_draws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("deck_id", sa.Integer(), nullable=True),
        sa.Column("deck_label", sa.String(), nullable=False),
        sa.Column("deck_type", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("cards", sa.JSON(), nullable=False),
        sa.Column("revealed", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deck_id"],
            ["decks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_draws_post_id"), "post_draws", ["post_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_post_draws_post_id"), table_name="post_draws")
    op.drop_table("post_draws")
    op.drop_index(op.f("ix_post_rolls_post_id"), table_name="post_rolls")
    op.drop_table("post_rolls")
