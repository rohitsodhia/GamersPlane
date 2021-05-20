from django.db import models
from django.core.cache import cache

from helpers.base_models import SoftDeleteModel, TimestampedModel
from helpers.cache import CacheKeys, CACHE_KEY_MAP, get_objects_by_id


class HeritageField(models.TextField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 25
        kwargs["null"] = True
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value == "":
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
    def children(self):
        children_ids = cache.get(
            CACHE_KEY_MAP[CacheKeys.FORUM_CHILDREN.value].format(id=id), []
        )
        if children_ids:
            cache.touch(CACHE_KEY_MAP[CacheKeys.FORUM_CHILDREN.value].format(id=id))
            children_objs: list[Forum] = get_objects_by_id(
                children_ids, Forum, CacheKeys.FORUM_DETAILS.value
            )
        else:
            children_objs = Forum.objects.filter(parent=self.id).order_by("order")
        children = [obj for obj in children_objs]
        return children
