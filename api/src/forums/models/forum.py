import functools
from typing import List

from django.db import models
from django.core.cache import cache

from helpers.base_models import SoftDeleteModel, TimestampedModel
from helpers.cache import CacheKeys, generate_cache_id, get_objects_by_id

from permissions.models.permission import Permission, FORUM_PERMISSION_PREFIX


FORUM_PERMISSIONS = [
    "moderate",
    "read",
    "write",
    "edit",
    "delete",
    "create_thread",
    "delete_thread",
    "rolls",
    "poll",
    "draws",
]


class HeritageField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 25
        kwargs["null"] = True
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if not value:
            return []
        return [int(id) for id in value.split("-")]

    def get_prep_value(self, value):
        if not value:
            return None
        return "-".join([str(forum_id).rjust(4, "0") for forum_id in value])


class Forum(SoftDeleteModel, TimestampedModel):
    class Meta:
        db_table = "forums"
        indexes = [models.Index(fields=["parent"]), models.Index(fields=["heritage"])]

    class ForumTypes(models.TextChoices):
        FORUM = "f", "Forum"
        CATEGORY = "c", "Category"

    title = models.CharField(max_length=200)
    description = models.TextField(null=True)
    forumType = models.CharField(
        max_length=1, choices=ForumTypes.choices, default=ForumTypes.FORUM, null=True
    )
    parent = models.ForeignKey(
        "forums.Forum", on_delete=models.PROTECT, db_column="parentId", null=True
    )
    heritage = HeritageField()
    order = models.IntegerField()
    game = models.ForeignKey(
        "games.Game", on_delete=models.PROTECT, db_column="gameId", null=True
    )
    threadCount = models.IntegerField(default=0)

    @property
    @functools.cache
    def children(self):
        children_ids = cache.get(
            generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id}), []
        )
        if children_ids:
            cache.touch(
                generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id})
            )
            children_objs: List[Forum] = get_objects_by_id(
                children_ids, Forum, CacheKeys.FORUM_DETAILS.value
            )
        else:
            children_objs = Forum.objects.filter(parent=self.id).order_by("order")
            cache.set(
                generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id}),
                [obj.id for obj in children_objs],
            )
        children = [obj for obj in children_objs]
        return children

    def save(self, *args, **kwargs):
        if not self.order:
            children_ids = cache.get(
                generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id}), []
            )
            if children_ids:
                num_children = len(children_ids)
                cache.touch(
                    generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id})
                )
            else:
                children = Forum.objects.filter(parent=self.parent.id)
                children_ids = []
                if children.count():
                    children_ids = [child["id"] for child in children.values("id")]
                    cache.set(
                        generate_cache_id(
                            CacheKeys.FORUM_CHILDREN.value, {"id": self.id}
                        ),
                        children_ids,
                    )
                num_children = len(children_ids)
            self.order = num_children + 1
        super().save(*args, **kwargs)

    def generate_heritage(self) -> None:
        if self.id:
            self.heritage = self.parent.heritage + [self.id]

    def user_permissions(self, permissions: list[Permission]):
        permissions_dict = {key: None for key in FORUM_PERMISSIONS}
        calculated_permissions = {
            forum_id: permissions_dict.copy() for forum_id in self.heritage
        }

        permission_starts = [
            "{FORUM_PERMISSION_PREFIX}{id}_" for id in self.heritage + self.children
        ]
        forum_permissions = filter(
            lambda permission: permission.startswith(tuple(permission_starts)),
            permissions,
        )

        for permission in forum_permissions:
            _, forum_id, *permission_val, grant = permission.split("_")
            permission_val = "_".join(permission_val)
            if grant == "revoke":
                calculated_permissions[forum_id][permission_val] = False
            elif (
                calculated_permissions[forum_id][permission_val] is None
                and grant == "add"
            ):
                calculated_permissions[forum_id][permission_val] = True

        for forum_id in self.heritage:
            for k, v in calculated_permissions[forum_id].items():
                if v == False:
                    permissions_dict[k] = False
                elif v == True and permissions_dict[k] != False:
                    permissions_dict[k] = True

        return permissions_dict
