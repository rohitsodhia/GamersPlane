from fastapi import APIRouter, status

from common.cache import CacheKeys, get_objects_by_id, set_cache
from common.functions import error_response

from common.decorators import logged_in

permissions = APIRouter(prefix="/permissions")


@logged_in
@permissions.get("/")
def list_permissions():

    pass
