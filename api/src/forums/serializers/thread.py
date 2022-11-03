from rest_framework import serializers

from forums.models import Thread, Post
from users.models import User


class ThreadPostAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        include = ["id", "username"]


class ThreadPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        include = [
            "id",
            "title",
            "author",
            "createdAt",
        ]


class ThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thread
        exclude = ["forum"]

    firstPost = ThreadPostSerializer()
    lastPost = ThreadPostSerializer()
