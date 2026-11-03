"""create forum subscriptions

Revision ID: b8e2f4a96d13
Revises: a9d3f5b27c14
Create Date: 2026-11-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8e2f4a96d13"
down_revision: Union[str, None] = "a9d3f5b27c14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forum_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("forum_id", sa.Integer(), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(forum_id IS NULL) <> (thread_id IS NULL)",
            name="ck_forum_subscriptions_forum_xor_thread",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["forum_id"], ["forums.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "forum_id", name="uq_forum_subscriptions_forum"),
        sa.UniqueConstraint(
            "user_id", "thread_id", name="uq_forum_subscriptions_thread"
        ),
    )
    op.create_index(
        op.f("ix_forum_subscriptions_user_id"), "forum_subscriptions", ["user_id"]
    )
    op.create_index(
        op.f("ix_forum_subscriptions_forum_id"), "forum_subscriptions", ["forum_id"]
    )
    op.create_index(
        op.f("ix_forum_subscriptions_thread_id"), "forum_subscriptions", ["thread_id"]
    )

    op.create_table(
        "forum_subscription_notices",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_through", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "thread_id"),
    )


def downgrade() -> None:
    op.drop_table("forum_subscription_notices")
    op.drop_index(
        op.f("ix_forum_subscriptions_thread_id"), table_name="forum_subscriptions"
    )
    op.drop_index(
        op.f("ix_forum_subscriptions_forum_id"), table_name="forum_subscriptions"
    )
    op.drop_index(
        op.f("ix_forum_subscriptions_user_id"), table_name="forum_subscriptions"
    )
    op.drop_table("forum_subscriptions")
