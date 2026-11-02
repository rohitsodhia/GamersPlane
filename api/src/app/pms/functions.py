import logging

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs import configs
from app.helpers.email import get_template, send_email
from app.helpers.prose import prose_snippet
from app.models import PM, UserMeta
from app.pms import schemas
from app.repositories import UserRepository

logger = logging.getLogger(__name__)

# The profile setting's label, as the profile page shows it.
PM_PREFERENCE_LABEL = "Receive PM emails?"
PM_TEMPLATE = "pms/templates/pm_received.html"
PM_PREVIEW_LENGTH = 300
PM_IMAGE_PLACEHOLDER = "[image]"


def build_pm_data(pm: PM) -> schemas.PM:
    return schemas.PM(
        id=pm.id,
        recipient=schemas.UserDetails(
            id=pm.recipient.id,
            username=pm.recipient.username,
            read=pm.recipient_read,
        ),
        sender=schemas.UserDetails(
            id=pm.sender.id, username=pm.sender.username, read=pm.sender_read
        ),
        title=pm.title,
        message=pm.message,
        datestamp=str(pm.datestamp),
        reply_to_id=pm.reply_to_id,
    )


def build_pm_preview(message: dict) -> str:
    """A plain-text preview of a PM body for the notification email."""
    return prose_snippet(
        message, PM_PREVIEW_LENGTH, image_placeholder=PM_IMAGE_PLACEHOLDER
    )


async def send_pm_email(
    recipient_email: str,
    *,
    pm_id: int,
    sender_username: str,
    title: str,
    preview: str,
) -> None:
    """Mail the recipient about a new PM. Takes plain values only: it runs as a
    background task, after the request's DB session is gone. ``preview`` is plain
    text; the template escapes it."""
    # Titles are stored with newlines as <br>
    title = title.replace("<br>", " ")
    content = get_template(
        PM_TEMPLATE,
        pm_id=pm_id,
        sender_username=sender_username,
        title=title,
        preview=preview,
        headline="New message",
        preference_label=PM_PREFERENCE_LABEL,
    )
    await send_email(recipient_email, f"New message from {sender_username}", content)


async def queue_pm_email(
    background_tasks: BackgroundTasks,
    db_session: AsyncSession,
    pm: PM,
    sender_username: str,
) -> None:
    """Tell a PM's recipient it arrived, honoring their pmMail preference
    (default on). Resolves the recipient now, inside the request, and schedules
    the send."""
    if not configs.EMAIL_ENABLED:
        logger.info(
            "Email disabled; would have mailed PM %s to user %s",
            pm.id,
            pm.recipient_id,
        )
        return
    recipients = await UserRepository(db_session).get_mail_recipients(
        [pm.recipient_id], UserMeta.MetaKeys.PM_MAIL
    )
    if not recipients:
        return
    background_tasks.add_task(
        send_pm_email,
        recipients[0],
        pm_id=pm.id,
        sender_username=sender_username,
        title=pm.title,
        preview=build_pm_preview(pm.message),
    )
