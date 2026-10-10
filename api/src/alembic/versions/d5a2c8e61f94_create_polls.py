"""create polls

Revision ID: d5a2c8e61f94
Revises: c4e9a1f27b3d
Create Date: 2026-10-10 09:20:11.402917

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5a2c8e61f94"
down_revision: Union[str, None] = "c4e9a1f27b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "polls",
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.String(length=200), nullable=False),
        sa.Column("options_per_user", sa.SmallInteger(), nullable=False),
        sa.Column("allow_revoting", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["threads.id"],
        ),
        sa.PrimaryKeyConstraint("thread_id"),
    )
    op.create_table(
        "poll_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["polls.thread_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_poll_options_thread_id"), "poll_options", ["thread_id"])
    op.create_table(
        "poll_votes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("option_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["poll_options.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "option_id"),
    )


def downgrade() -> None:
    op.drop_table("poll_votes")
    op.drop_index(op.f("ix_poll_options_thread_id"), table_name="poll_options")
    op.drop_table("poll_options")
    op.drop_table("polls")
