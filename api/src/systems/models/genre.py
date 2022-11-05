from django.db import models
from common.base_models import TimestampedModel, SoftDeleteModel


class Genre(SoftDeleteModel, TimestampedModel):
    class Meta:
        db_table = "genres"

    genre = models.CharField(max_length=40)
