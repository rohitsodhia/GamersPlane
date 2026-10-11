from email.utils import formataddr

from fastapi import APIRouter, Request, status

from app.configs import configs
from app.contact import rate_limit
from app.contact.schemas import ContactInput
from app.helpers.decorators import public
from app.helpers.email import get_template, send_email
from app.helpers.functions import error_response
from app.schemas import ErrorItem

contact = APIRouter(prefix="/contact")


@contact.post("")
@public
async def send_contact(request: Request, data: ContactInput):
    # Bots that fill the hidden field get a normal-looking success and nothing sent
    if data.website:
        return {"success": True}

    if not rate_limit.allow(rate_limit.client_ip(request)):
        return error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            errors=[
                ErrorItem(
                    code="rate_limited",
                    detail="You've sent several messages recently. Please try again later.",
                )
            ],
        )

    user = request.scope.get("user")
    content = get_template(
        "contact/templates/contact.html",
        name=data.name,
        email=data.email,
        user_id=user.id if user else None,
        # A logged-in user's own username replaces whatever was submitted
        username=user.username if user else data.username,
        subject=data.subject,
        message=data.message,
    )
    await send_email(
        configs.CONTACT_EMAIL,
        f"Gamers' Plane Contact: {data.subject}",
        content,
        reply_to=formataddr((data.name, data.email)),
    )

    return {"success": True}
