from fastapi.routing import APIRoute

from app.main import create_app

# Everything not listed here requires login, enforced by
# middleware.check_authorization (tested in test_middleware.py), so adding a
# public route must be a deliberate edit to this set.
EXPECTED_PUBLIC_ROUTES = {
    ("POST", "/auth/login"),
    ("POST", "/auth/register"),
    ("POST", "/auth/resendActivation"),
    ("POST", "/auth/activate/{token}"),
    ("GET", "/auth/password_reset"),
    ("POST", "/auth/password_reset"),
    ("PATCH", "/auth/password_reset"),
    ("POST", "/contact"),
    ("GET", "/faqs"),
    ("GET", "/forums/search"),
    ("GET", "/forums/{forum_id}"),
    ("GET", "/forums/{forum_id}/breadcrumbs"),
    ("GET", "/games/"),
    ("GET", "/games/latest"),
    ("GET", "/games/{game_id}"),
    ("GET", "/posts"),
    ("GET", "/referral_links/"),
    ("GET", "/systems/"),
    ("GET", "/systems/basic"),
    ("GET", "/threads"),
    ("GET", "/threads/search"),
    ("GET", "/threads/{thread_id}"),
    ("GET", "/tools/dice"),
    ("GET", "/users/moderators"),
    ("GET", "/users/{id}"),
}


def test_only_expected_routes_are_public():
    app = create_app(init_db=False)

    public_routes = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        and ".legacy" not in route.endpoint.__module__
        and getattr(route.endpoint, "is_public", False)
        for method in route.methods
    }

    assert public_routes == EXPECTED_PUBLIC_ROUTES
