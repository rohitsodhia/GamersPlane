from typing import Optional

import inflect
from fastapi.responses import JSONResponse

inflectEngine = inflect.engine()


def error_response(status_code: int, content: Optional[dict] = None) -> JSONResponse:
    if content == None:
        content = {}
    return JSONResponse(status_code=status_code, content={"errors": content})


def pluralize(word: inflect.Word) -> str:
    return inflectEngine.plural(word)
