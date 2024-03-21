import smtplib

from jinja2 import FileSystemLoader, Environment

import envs

from email.message import EmailMessage
from email.headerregistry import Address


uri = envs.EMAIL_URI


def get_template(template: str, **kwargs) -> str:
    file_loader = FileSystemLoader(searchpath=envs.ROOT_DIR)
    env = Environment(loader=file_loader)

    template = env.get_template(template)

    output = template.render(site_domain=envs.HOST_NAME, **kwargs)
    return output


def send_email(to: str, subject: str, content: str, html: bool = True) -> None:
    if envs.ENVIRONMENT == "dev":
        return

    if html:
        subtype = "html"
    else:
        subtype = "plain"

    email = EmailMessage()
    email["From"] = Address(
        display_name="No Reply (Gamers' Plane)",
        username="no-reply",
        domain="gamersplane.com",
    )
    email["To"] = to
    email["Subject"] = subject
    email.set_content(content, subtype=subtype)

    with smtplib.SMTP(uri) as server:
        server.send_message(email)
