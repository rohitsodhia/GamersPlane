from sqlalchemy import select

from app.models import ReferralLink


class ReferralLinkRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_referral_links(self) -> list[ReferralLink] | None:
        links = await self.db_session.scalar(
            select(ReferralLink)
            .where(ReferralLink.enabled)
            .order_by(ReferralLink.order)
        )
        return links
