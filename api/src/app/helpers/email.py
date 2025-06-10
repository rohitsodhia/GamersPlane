import smtplib
from email.headerregistry import Address
from email.message import EmailMessage

from jinja2 import Environment, FileSystemLoader

from app.configs import configs

# uri = configs.EMAIL_URI
# port = configs.EMAIL_PORT
# login = configs.EMAIL_LOGIN
# password = configs.EMAIL_PASSWORD

# context = ssl.create_default_context()


def get_template(template_path: str, **kwargs) -> str:
    file_loader = FileSystemLoader(searchpath=configs.ROOT_DIR)
    env = Environment(loader=file_loader)

    template = env.get_template(template_path)

    output = template.render(site_domain=configs.HOST_NAME, **kwargs)
    return output


def send_email(to: str, subject: str, content: str) -> None:
    if configs.ENVIRONMENT == "dev":
        return

    email = EmailMessage()
    email["From"] = Address(
        display_name="No Reply (Gamers' Plane)",
        username="no-reply",
        domain="gamersplane.com",
    )
    email["To"] = to
    email["Subject"] = subject
    email.set_content(content, subtype="html")

    # with smtplib.SMTP_SSL(uri, port, context=context) as server:
    #     server.login(login, password)
    with smtplib.SMTP("localhost") as server:
        server.send_message(email)
