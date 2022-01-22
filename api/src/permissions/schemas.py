from typing import List
from pydantic import BaseModel


class OwnerData(BaseModel):
    id: int
    username: str


class RoleData(BaseModel):
    id: int
    name: str
    owner: OwnerData
    member: bool
    admin: bool


class RoleListResponse(BaseModel):
    roles: List[RoleData]
