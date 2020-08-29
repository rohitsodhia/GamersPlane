import random
import string
from datetime import datetime

from django.db import models

from auth.models import User


class TokenQuerySet(models.QuerySet):
    def use(self):
        return super().update(used=datetime.utcnow())

    def available(self):
        return super().filter(used=None)


class TokenManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.available = kwargs.pop("available", True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if self.available:
            return TokenQuerySet(self.model).available()
        return TokenQuerySet(self.model)


class Token(models.Model):
    class Meta:
        db_table = "tokens"
        indexes = [models.Index(fields=["token"])]

    class TokenTypes(models.TextChoices):
        ACCOUNT_ACTIVATION = "aa", "Account Activation"
        PASSWORD_RESET = "pr", "Password Reset"

    user = models.ForeignKey(User, db_column="userId", on_delete=models.PROTECT)
    token_type = models.CharField(max_length=2, choices=TokenTypes.choices)
    token = models.CharField(max_length=16)
    requestedOn = models.DateTimeField(auto_now_add=True)
    used = models.DateTimeField(null=True, default=None)

    objects = TokenManager()
    all_objects = TokenManager(available=False)

    def generate_token(self):
        if self.token:
            return
        lettersAndDigits = string.ascii_letters + string.digits
        self.token = "".join(random.choices(lettersAndDigits, k=16))

    @staticmethod
    def validate_token(token, email=None, get_obj=False):
        token = Token.objects.filter(token=token)
        if email:
            token = token.filter(user__email=email)

        if get_obj:
            return token[0] if token else None
        return True if token else False