"""create events

Revision ID: c6d1e8a35f27
Revises: b8e2f4a96d13
Create Date: 2026-11-03 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c6d1e8a35f27"
down_revision: Union[str, None] = "b8e2f4a96d13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(type = 'mention' AND post_id IS NOT NULL AND thread_id IS NOT NULL)"
            " OR (type IN ('game_invite', 'game_application')"
            " AND game_id IS NOT NULL AND subject_user_id IS NOT NULL)"
            " OR (type = 'character_submitted'"
            " AND game_id IS NOT NULL AND character_id IS NOT NULL)",
            name="ck_events_type_columns",
        ),
    )
    # One event per post's mentions, per invited or applying user in a game, and
    # per submitted character; a repeat reuses the event.
    op.create_index(
        "uq_events_mention_post",
        "events",
        ["post_id"],
        unique=True,
        postgresql_where=sa.text("type = 'mention'"),
    )
    op.create_index(
        "uq_events_game_subject",
        "events",
        ["type", "game_id", "subject_user_id"],
        unique=True,
        postgresql_where=sa.text("type IN ('game_invite', 'game_application')"),
    )
    op.create_index(
        "uq_events_character",
        "events",
        ["character_id"],
        unique=True,
        postgresql_where=sa.text("type = 'character_submitted'"),
    )
    op.create_table(
        "event_recipients",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("event_id", "user_id"),
    )
    op.create_index(
        "ix_event_recipients_user_id_read_at",
        "event_recipients",
        ["user_id", "read_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_recipients_user_id_read_at", table_name="event_recipients")
    op.drop_table("event_recipients")
    op.drop_index("uq_events_character", table_name="events")
    op.drop_index("uq_events_game_subject", table_name="events")
    op.drop_index("uq_events_mention_post", table_name="events")
    op.drop_table("events")
