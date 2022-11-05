from django.db import models

from common.base_models import SoftDeleteModel, TimestampedModel


class Thread(SoftDeleteModel, TimestampedModel):
    class Meta:
        db_table = "threads"

    forum = models.ForeignKey(
        "forums.Forum", on_delete=models.PROTECT, db_column="forumId"
    )
    sticky = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)
    allowRolls = models.BooleanField(default=False)
    allowDraws = models.BooleanField(default=False)
    firstPost = models.ForeignKey(
        "forums.Post",
        on_delete=models.PROTECT,
        db_column="firstPostId",
        related_name="first_post",
        null=True,
        blank=True,
    )
    lastPost = models.ForeignKey(
        "forums.Post",
        on_delete=models.PROTECT,
        db_column="lastPostId",
        related_name="last_post",
        null=True,
        blank=True,
    )
    postCount = models.IntegerField(default=0)
