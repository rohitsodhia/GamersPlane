def public(route_handler):
    route_handler.is_public = True
    return route_handler


def requires(*permissions: str):
    """Restrict a route to users holding at least one of these global permission verbs.

    Checked centrally by ``check_authorization`` against ``request.scope["auth"]``.
    Holding the ``admin`` verb satisfies any such check (see ``ADMIN_OVERRIDE`` in
    ``app.middleware``). Place below the router decorator:

        @router.get("/roles")
        @requires("access_acp")
        async def list_roles(...): ...
    """

    def decorator(route_handler):
        route_handler.required_permissions = frozenset(permissions)
        return route_handler

    return decorator
