import pytest

from tests.conftest import SITE_ROOT_FORUM_ID


@pytest.fixture(autouse=True)
async def _open_site_root(wrap_in_savepoint, open_forums):
    """Start every route test with ordinary member access under the site root."""
    await open_forums(SITE_ROOT_FORUM_ID)
