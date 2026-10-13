"""create NPC images and quick NPCs

Revision ID: e7b3d94a1c52
Revises: d5a2c8e61f94
Create Date: 2026-10-10 14:05:33.118204

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7b3d94a1c52"
down_revision: Union[str, None] = "d5a2c8e61f94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "npc_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ext", sa.String(length=5), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(game_id IS NULL) <> (user_id IS NULL)",
            name="ck_npc_images_one_owner",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_npc_images_game_id"), "npc_images", ["game_id"])
    op.create_index(op.f("ix_npc_images_user_id"), "npc_images", ["user_id"])
    op.create_table(
        "quick_npcs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(game_id IS NULL) <> (user_id IS NULL)",
            name="ck_quick_npcs_one_owner",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["npc_images.id"],
            name="quick_npcs_image_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quick_npcs_game_id"), "quick_npcs", ["game_id"])
    op.create_index(op.f("ix_quick_npcs_user_id"), "quick_npcs", ["user_id"])
    # One live pair per (owner, name, image); a missing image counts as equal.
    op.create_index(
        "uq_quick_npcs_owner_name_image_id",
        "quick_npcs",
        ["game_id", "user_id", "name", "image_id"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("deleted IS NULL"),
    )
    op.create_foreign_key(
        "posts_posted_npc_id_fkey",
        "posts",
        "quick_npcs",
        ["posted_npc_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_posts_posted_as_xor_npc",
        "posts",
        "posted_as_id IS NULL OR posted_npc_id IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_posts_posted_as_xor_npc", "posts", type_="check")
    op.drop_constraint("posts_posted_npc_id_fkey", "posts", type_="foreignkey")
    op.drop_index(
        "uq_quick_npcs_owner_name_image_id",
        table_name="quick_npcs",
        postgresql_where=sa.text("deleted IS NULL"),
    )
    op.drop_index(op.f("ix_quick_npcs_user_id"), table_name="quick_npcs")
    op.drop_index(op.f("ix_quick_npcs_game_id"), table_name="quick_npcs")
    op.drop_table("quick_npcs")
    op.drop_index(op.f("ix_npc_images_user_id"), table_name="npc_images")
    op.drop_index(op.f("ix_npc_images_game_id"), table_name="npc_images")
    op.drop_table("npc_images")
