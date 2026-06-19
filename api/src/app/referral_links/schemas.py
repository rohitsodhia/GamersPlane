from pydantic import HttpUrl

from app.schema_base import SchemaBase


class ReferralLinkSchema(SchemaBase):
    key: int
    title: str
    link: HttpUrl
    order: int


class GetReferralLinksResponse(SchemaBase):
    referralLinks: list[ReferralLinkSchema]
