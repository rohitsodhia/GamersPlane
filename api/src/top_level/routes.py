from fastapi import APIRouter

from helpers.email import send_email

from top_level import schemas

top_level = APIRouter()


@top_level.post("/contact")
def contact(contact_values: schemas.ContactInput):
    message = (
        f"name: {contact_values.name}\n"
        f"username: {contact_values.username}\n"
        f"email: {contact_values.email}\n"
        f"subject: {contact_values.subject}\n"
        f"message:\n\n{contact_values.message}"
    )
    send_email(
        contact_values.email,
        f"Gamers' Plane Contact: {contact_values.subject}",
        message,
    )
    return {"success": True}


# @tools.route("/dice", methods=["GET"])
# def roll_dice():
