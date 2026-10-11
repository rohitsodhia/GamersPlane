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


async def send_email(to: str, subject: str, content: str) -> None:
    """Send an HTML email. Failures are logged and swallowed, never raised."""
    if not configs.EMAIL_ENABLED:
        logger.info("Email disabled; not sending to %s: %s\n%s", to, subject, content)
        return

    email = EmailMessage()
    email["From"] = Address(
        display_name="No Reply (Gamers' Plane)",
        username="no-reply",
        domain=configs.EMAIL_DOMAIN,
    )
    email["To"] = to
    email["Subject"] = subject
    # Postfix doesn't add these for mail from non-local clients
    email["Date"] = formatdate(localtime=False)
    email["Message-ID"] = make_msgid(domain=configs.EMAIL_DOMAIN)
    email.set_content(content, subtype="html")

    try:
        await aiosmtplib.send(
            email, hostname=configs.EMAIL_HOST, port=configs.EMAIL_PORT
        )
    except (aiosmtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s: %s", to, subject)
