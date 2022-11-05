import bcrypt
import datetime
import functools
import jwt
from typing import List

from django.core.cache import cache
from django.db import models, connection

from envs import JWT_ALGORITHM, JWT_SECRET_KEY
from common.cache import generate_cache_id, CacheKeys
from permissions.models.permission import FORUM_PERMISSION_PREFIX


class UserManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.inactive = kwargs.pop("inactive", False)
        self.banned = kwargs.pop("banned", False)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        queryset = models.QuerySet(self.model)
        if not self.inactive:
            queryset = queryset.filter(activatedOn__isnull=False)
        if not self.banned:
            queryset = queryset.filter(banned__isnull=True)
        return queryset


class User(models.Model):
    class Meta:
        db_table = "users"

    username = models.CharField(max_length=24, unique=True)
    password = models.CharField(max_length=64)
    email = models.CharField(max_length=50, unique=True)
    avatar_id = models.UUIDField(null=True, db_column="avatar")
    joinDate = models.DateTimeField(auto_now=True)
    activatedOn = models.DateTimeField(null=True)
    lastActivity = models.DateTimeField(null=True)
    suspendedUntil = models.DateTimeField(null=True)
    banned = models.DateTimeField(null=True)
    roles = models.ManyToManyField(
        "permissions.Role", related_name="users", through="users.UserRoles"
    )
    admin = models.BooleanField(default=False)

    objects = UserManager()
    all_objects = UserManager(inactive=True, banned=True)

    MIN_PASSWORD_LENGTH = 8

    @property
    def avatar(self):
        if not self.avatar_id:
            return "default.png"
        return self.avatar_id + ".png"

    def _get_permissions(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT permission FROM permissions p INNER JOIN role_permissions rp ON rp.permissionId = p.id INNER JOIN roles r ON r.id = rp.roleId INNER JOIN user_roles ur ON ur.roleId = r.id WHERE ur.userId = %s",
                [self.id],
            )
            permissions = cursor.fetchall()
        return list([v[0] for v in permissions])

    @property
    @functools.cache
    def permissions(self) -> List[int]:
        permissions = cache.get_or_set(
            generate_cache_id(CacheKeys.USER_PERMISSIONS.value, {"id": self.id}),
            self._get_permissions,
        )
        return permissions

    @functools.cache
    def get_forum_permissions(self):
        return [
            permission
            for permission in self.permissions
            if permission.startswith(FORUM_PERMISSION_PREFIX)
        ]

    @staticmethod
    def validate_password(password: str) -> list:
        invalid = []
        if len(password) < User.MIN_PASSWORD_LENGTH:
            invalid.append("pass_too_short")
        return invalid

    @staticmethod
    def hash_pass(password: str) -> str:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        return hashed.decode("utf-8")

    def set_password(self, password: str) -> bool:
        pass_valid = User.validate_password(password)
        if pass_valid == []:
            self.password = self.hash_pass(password)
            return True
        return False

    def activate(self):
        self.activatedOn = datetime.datetime.utcnow()
        self.save()
        return self

    def check_pass(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.password.encode("utf-8"))

    def generate_jwt(self, exp_len: int = None) -> str:
        if not exp_len:
            exp_len = {"weeks": 2}
        return jwt.encode(
            {
                "user_id": self.id,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(**exp_len),
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )

    def to_dict(self):
        dict_val = {
            "username": self.username,
            "email": self.email,
            "joinDate": self.joinDate,
            "lastActivity": self.lastActivity,
            "suspendedUntil": self.suspendedUntil,
            "banned": self.banned,
            "roles": [v.name for v in self.roles.all()],
            "permissions": self.permissions,
            "admin": self.admin,
        }
        return dict_val
