from app.models import PM
from app.pms import schemas


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
