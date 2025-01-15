from fastapi import APIRouter, status
from helpers.cache import CacheKeys, get_objects_by_id, set_cache
from helpers.decorators import logged_in
from helpers.functions import error_response

permissions = APIRouter(prefix="/permissions")


@logged_in
@permissions.get("/")
def list_permissions():

    pass
