from fastapi import APIRouter

from app.models import ReferralLink
from app.referral_links import schemas

referral_links = APIRouter(prefix="/referral_links")


@referral_links.get("/", response_model=schemas.GetReferralLinksResponse)
def get_referral_links():
    links = ReferralLink.objects.order_by("order").values()
    return {"referralLinks": [link for link in links]}
