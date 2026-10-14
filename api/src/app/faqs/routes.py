from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.exceptions import NotFoundException
from app.faqs import schemas
from app.helpers.decorators import public, requires
from app.models import FAQ
from app.repositories import FAQRepository

faqs = APIRouter(prefix="/faqs")


async def get_faq_or_404(faq_repository: FAQRepository, faq_id: int) -> FAQ:
    faq = await faq_repository.get(faq_id)
    if faq is None:
        raise NotFoundException("FAQ not found")
    return faq


@faqs.get("", response_model=schemas.GetFAQsResponse)
@public
async def get_faqs(db_session: DBSessionDependency):
    """Every category, in display order (empty ones included), with its FAQs."""
    all_faqs = await FAQRepository(db_session).get_all()
    return {
        "categories": [
            {
                "category": category,
                "label": category.label,
                "faqs": [faq for faq in all_faqs if faq.category == category],
            }
            for category in FAQ.Categories
        ]
    }


@faqs.post("", response_model=schemas.FAQData, status_code=status.HTTP_201_CREATED)
@requires("manage_faqs")
async def create_faq(data: schemas.FAQInput, db_session: DBSessionDependency):
    return await FAQRepository(db_session).add(
        data.category, data.question, data.answer
    )


@faqs.put("/{faq_id}", response_model=schemas.FAQData)
@requires("manage_faqs")
async def update_faq(
    faq_id: int, data: schemas.FAQInput, db_session: DBSessionDependency
):
    faq_repository = FAQRepository(db_session)
    faq = await get_faq_or_404(faq_repository, faq_id)
    return await faq_repository.update(faq, data.category, data.question, data.answer)


@faqs.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
@requires("manage_faqs")
async def delete_faq(faq_id: int, db_session: DBSessionDependency):
    faq_repository = FAQRepository(db_session)
    faq = await get_faq_or_404(faq_repository, faq_id)
    await faq_repository.delete(faq)


@faqs.post("/{faq_id}/move", status_code=status.HTTP_204_NO_CONTENT)
@requires("manage_faqs")
async def move_faq(
    faq_id: int, data: schemas.MoveFAQInput, db_session: DBSessionDependency
):
    faq_repository = FAQRepository(db_session)
    faq = await get_faq_or_404(faq_repository, faq_id)
    await faq_repository.move(faq, data.direction)
