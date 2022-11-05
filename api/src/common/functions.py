from fastapi.responses import JSONResponse
import inflect

infe = inflect.engine()


def error_response(status_code: int, content: dict = None) -> JSONResponse:
    if content == None:
        content = {}
    return JSONResponse(status_code=status_code, content={"errors": content})


def pluralize(word: str) -> str:
    return infe.plural(word)
