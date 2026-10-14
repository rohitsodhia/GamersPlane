from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from app.models import FAQ
from app.schema_base import SchemaBase

# Plain text, trimmed before the length check so a blank question is rejected.
FAQQuestion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


def _has_content(node: object) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get("type") == "text":
        return bool((node.get("text") or "").strip())
    if node.get("type") not in (None, "doc", "paragraph"):
        # Any other node (image, list, rule...) counts as content.
        return True
    content = node.get("content")
    return isinstance(content, list) and any(_has_content(child) for child in content)


class FAQInput(SchemaBase):
    category: FAQ.Categories
    question: FAQQuestion
    answer: dict

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, value: dict) -> dict:
        if value.get("type") != "doc" or not _has_content(value):
            raise ValueError("An answer is required")
        return value


class MoveFAQInput(SchemaBase):
    direction: Literal["up", "down"]


class FAQData(SchemaBase):
    id: int
    category: FAQ.Categories
    question: str
    answer: dict
    order: int


class FAQCategoryData(SchemaBase):
    category: FAQ.Categories
    label: str
    faqs: list[FAQData]


class GetFAQsResponse(SchemaBase):
    categories: list[FAQCategoryData]
