from fastapi.responses import JSONResponse
import inflect

infe = inflect.engine()


def error_response(code: int, content: dict) -> JSONResponse:
    return JSONResponse(status_code=code, content={"errors": content})


def pluralize(word: str) -> str:
    return infe.plural(word)
