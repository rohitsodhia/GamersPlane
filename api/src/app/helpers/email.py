import logging
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.configs import configs

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).parent.parent

_env = Environment(
    loader=FileSystemLoader(searchpath=str(_APP_DIR)),
    autoescape=select_autoescape(["html"]),
)


def get_template(template_path: str, **kwargs) -> str:
    template = _env.get_template(template_path)

    output = template.render(site_domain=configs.HOST_NAME, **kwargs)
    return output


BCC_BATCH_SIZE = 100


def _build_message(
    to: str,
    subject: str,
    content: str,
    reply_to: str | None,
    bcc: list[str] | None,
) -> EmailMessage:
    email = EmailMessage()
    email["From"] = Address(
        display_name="No Reply (Gamers' Plane)",
        username="no-reply",
        domain=configs.EMAIL_DOMAIN,
    )
    email["To"] = to
    if bcc:
        # aiosmtplib adds Bcc addresses to the envelope and strips the header
        email["Bcc"] = ", ".join(bcc)
    email["Subject"] = subject
    if reply_to:
        email["Reply-To"] = reply_to
    # Postfix doesn't add these for mail from non-local clients
    email["Date"] = formatdate(localtime=False)
    email["Message-ID"] = make_msgid(domain=configs.EMAIL_DOMAIN)
    email.set_content(content, subtype="html")
    return email


async def send_email(
    to: str,
    subject: str,
    content: str,
    *,
    reply_to: str | None = None,
    bcc: list[str] | None = None,
    mass: bool = False,
) -> None:
    """Send an HTML email. Failures are logged and swallowed, never raised.

    `reply_to` is a ready-made header value (e.g. from `email.utils.formataddr`).
    `bcc` addresses are sent in batches of `BCC_BATCH_SIZE`, one message per
    batch. `mass` messages additionally need `MASS_EMAIL_ENABLED`, so
    non-production data can't mail real users."""
    if mass and not (configs.EMAIL_ENABLED and configs.MASS_EMAIL_ENABLED):
        logger.info(
            "Mass email disabled; not sending to %d recipients: %s",
            len(bcc or []) + 1,
            subject,
        )
        return
    if not configs.EMAIL_ENABLED:
        logger.info("Email disabled; not sending to %s: %s\n%s", to, subject, content)
        return

    batches = (
        [bcc[i : i + BCC_BATCH_SIZE] for i in range(0, len(bcc), BCC_BATCH_SIZE)]
        if bcc
        else [None]
    )
    for batch in batches:
        email = _build_message(to, subject, content, reply_to, batch)
        try:
            await aiosmtplib.send(
                email, hostname=configs.EMAIL_HOST, port=configs.EMAIL_PORT
            )
        except (aiosmtplib.SMTPException, OSError):
            logger.exception("Failed to send email to %s: %s", to, subject)
