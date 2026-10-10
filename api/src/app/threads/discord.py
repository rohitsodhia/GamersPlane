"""Posting a thread's new and edited posts to its Discord webhook."""

import logging

import httpx
from fastapi import BackgroundTasks

from app.configs import configs
from app.helpers.prose import prose_snippet
from app.models import Post, User
from app.repositories import PostRepository
from app.threads.option_schemas import DISCORD_WEBHOOK_PATTERN

logger = logging.getLogger(__name__)

EMBED_COLOR = 13395456  # #cc6600
DESCRIPTION_LIMIT = 200
TIMEOUT_SECONDS = 5.0


def build_post_payload(
    post: Post, author: User, thread_id: int, page: int, *, edited: bool = False
) -> dict:
    """The webhook body for a post, as plain data so it outlives the DB session."""
    title = post.title.removeprefix("Re: ")
    # Where a character's name and avatar would replace the author's, once
    # ``Post.posted_as`` is actually set by something.
    payload: dict = {"username": author.username}
    # The avatar is a URL built from config; skip it rather than send a broken one.
    if author.avatar_url.startswith(("http://", "https://")):
        payload["avatar_url"] = author.avatar_url
    payload["embeds"] = [
        {
            "title": title,
            "url": f"{configs.HOST_NAME}/forums/thread/{thread_id}?page={page}#post-{post.id}",
            "description": prose_snippet(post.body, DESCRIPTION_LIMIT),
            "color": EMBED_COLOR,
            "footer": {"text": author.username + (" ~ edited post" if edited else "")},
        }
    ]
    return payload


async def send_webhook(url: str, payload: dict) -> None:
    """POST ``payload`` to ``url``. Fire-and-forget: failures are only logged."""
    # Stored values come from before the pattern was enforced, so check again
    # right before sending; this must never POST to an arbitrary host.
    if not DISCORD_WEBHOOK_PATTERN.fullmatch(url):
        return
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
        if not response.is_success:
            logger.warning("Discord webhook returned %s", response.status_code)
    except Exception:
        logger.warning("Discord webhook failed", exc_info=True)


async def queue_post_webhook(
    background_tasks: BackgroundTasks,
    post_repository: PostRepository,
    webhook: str | None,
    post: Post,
    author: User,
    *,
    edited: bool = False,
) -> None:
    """Schedule ``post`` to be sent to ``webhook`` once the response is out.

    Does nothing for an unset or invalid webhook, or an unpublished post.
    """
    if (
        not webhook
        or not DISCORD_WEBHOOK_PATTERN.fullmatch(webhook)
        or post.state != Post.States.PUBLISHED
    ):
        return
    page = await post_repository.get_page_number(post)
    payload = build_post_payload(post, author, post.thread_id, page, edited=edited)
    background_tasks.add_task(send_webhook, webhook, payload)
