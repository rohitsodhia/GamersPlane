from typing import List, Dict

from pydantic import BaseModel, HttpUrl


class ReferralLinkSchema(BaseModel):
    key = str
    title = str
    link = HttpUrl
    order = int
    enabled = bool


class GetReferralLinksResponse(BaseModel):
    referralLinks: List[ReferralLinkSchema]
