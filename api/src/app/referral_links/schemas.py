from pydantic import BaseModel, HttpUrl


class ReferralLinkSchema(BaseModel):
    key: str
    title: str
    link: HttpUrl
    order: int


class GetReferralLinksResponse(BaseModel):
    referralLinks: list[ReferralLinkSchema]
