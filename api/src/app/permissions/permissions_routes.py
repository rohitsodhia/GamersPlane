from fastapi import APIRouter
from helpers.decorators import logged_in

permissions = APIRouter(prefix="/permissions")


@logged_in
@permissions.get("/")
def list_permissions():
    pass
