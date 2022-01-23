from fastapi import APIRouter

from referral_links import schemas
from referral_links.models import ReferralLink

referral_links = APIRouter(prefix="/referral_links")


@referral_links.get("/", response_model=schemas.GetReferralLinksResponse)
def get_referral_links():
    links = ReferralLink.objects.order_by("order").values()
    return {"referralLinks": [link for link in links]}
