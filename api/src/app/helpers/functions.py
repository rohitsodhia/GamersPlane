import inflect
from fastapi.responses import JSONResponse

inflectEngine = inflect.engine()


def error_response(status_code: int, content: dict | None = None) -> JSONResponse:
    if content is None:
        content = {}
    return JSONResponse(status_code=status_code, content={"errors": content})


def pluralize(word: inflect.Word) -> str:
    return inflectEngine.plural(word)
