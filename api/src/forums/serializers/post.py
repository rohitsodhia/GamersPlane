from rest_framework import serializers

from forums.models import Post
from users.models.user import User


class PostAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "lastActivity",
            "suspendedUntil",
            "banned",
        ]


class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = "__all__"

    author = PostAuthorSerializer()
