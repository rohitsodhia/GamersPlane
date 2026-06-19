from fastapi import APIRouter

from app.database import DBSessionDependency
from app.helpers.decorators import public
from app.referral_links import schemas
from app.repositories import ReferralLinkRepository

referral_links = APIRouter(prefix="/referral_links")


@referral_links.get("/", response_model=schemas.GetReferralLinksResponse)
@public
async def get_referral_links(db_session: DBSessionDependency):
    referral_link_repository = ReferralLinkRepository(db_session)
    referral_links = await referral_link_repository.get_all()
    return {"referralLinks": referral_links or []}
