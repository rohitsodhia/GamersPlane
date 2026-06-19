from sqlalchemy import select

from app.models import ReferralLink


class ReferralLinkRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_all(self) -> list[ReferralLink] | None:
        links = await self.db_session.scalars(
            select(ReferralLink)
            .where(ReferralLink.enabled)
            .order_by(ReferralLink.order)
        )
        return links.all()

    async def add(
        self,
        title: str,
        link: str,
        order: int,
        enabled: bool = True,
    ):
        referral_link = ReferralLink(
            title=title,
            link=link,
            order=order,
            enabled=enabled,
        )
        self.db_session.add(referral_link)
        await self.db_session.flush()
