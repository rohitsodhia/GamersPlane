from functools import partial, wraps
from typing import Callable

from fastapi import status
from helpers.functions import error_response


def public(route_handler):
    route_handler.is_public = True
    return route_handler


def logged_in(func=None, *, permissions=None):
    if func is None:
        return partial(logged_in, permissions=permissions)

    @wraps(func)
    def wrapper(*args, **kwargs) -> Callable:
        nonlocal permissions
        if not globals.current_user:
            return error_response(status_code=status.HTTP_401_UNAUTHORIZED)
        if permissions:
            if type(permissions) == str:
                permissions = [permissions]
            if not globals.current_user.admin and not bool(
                set(globals.current_user.permissions) & set(permissions)
            ):
                return error_response(status_code=status.HTTP_403_FORBIDDEN)
        return func(*args, **kwargs)

    return wrapper
