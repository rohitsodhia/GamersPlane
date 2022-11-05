from django.db import models
from common.base_models import TimestampedModel, SoftDeleteModel


class Publisher(SoftDeleteModel, TimestampedModel):
    class Meta:
        db_table = "publishers"

    name = models.CharField(max_length=40)
    website = models.CharField(max_length=200, null=True)
