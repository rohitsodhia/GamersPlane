"""Create thread, post, and character models

Revision ID: 43a15a5a15ae
Revises: 3217bdd97916
Create Date: 2026-08-10 02:21:46.422625

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "43a15a5a15ae"
down_revision: Union[str, None] = "3217bdd97916"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("system_id", sa.String(length=20), nullable=False),
        sa.Column("type", sa.String(length=5), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("deleted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["systems.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=1), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_of_id", sa.Integer(), nullable=True),
        sa.Column("posted_as_id", sa.Integer(), nullable=True),
        sa.Column("deleted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["posted_as_id"],
            ["characters.id"],
        ),
        sa.ForeignKeyConstraint(
            ["revision_of_id"],
            ["posts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posts_thread_id"), "posts", ["thread_id"], unique=False)
    op.create_table(
        "threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("forum_id", sa.Integer(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("first_post_id", sa.Integer(), nullable=True),
        sa.Column("last_post_id", sa.Integer(), nullable=True),
        sa.Column("post_count", sa.Integer(), nullable=False),
        sa.Column("deleted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["first_post_id"],
            ["posts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["forum_id"],
            ["forums.id"],
        ),
        sa.ForeignKeyConstraint(
            ["last_post_id"],
            ["posts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_threads_forum_id"), "threads", ["forum_id"], unique=False)
    op.create_foreign_key(
        "fk_posts_thread_id_threads", "posts", "threads", ["thread_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_posts_thread_id_threads", "posts", type_="foreignkey")
    op.drop_index(op.f("ix_threads_forum_id"), table_name="threads")
    op.drop_table("threads")
    op.drop_index(op.f("ix_posts_thread_id"), table_name="posts")
    op.drop_table("posts")
    op.drop_table("characters")
