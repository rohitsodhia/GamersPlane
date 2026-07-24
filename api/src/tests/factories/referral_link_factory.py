from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import Sequence

from app.models import ReferralLink


class ReferralLinkFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[misc]
        model = ReferralLink

    title = Sequence(lambda n: f"Referral Link {n}")
    link = Sequence(lambda n: f"https://example{n}.com")
    order = Sequence(lambda n: n)
    enabled = True
