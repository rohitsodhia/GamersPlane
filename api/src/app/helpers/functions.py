import inflect
from fastapi.responses import JSONResponse

from app.schemas import ErrorItem

inflectEngine = inflect.engine()


def error_response(status_code: int, errors: list[ErrorItem]) -> JSONResponse:
    serialized_errors = [e.model_dump(exclude_none=True) for e in (errors or [])]
    return JSONResponse(status_code=status_code, content={"errors": serialized_errors})


def pluralize(word: inflect.Word) -> str:
    return inflectEngine.plural(word)
