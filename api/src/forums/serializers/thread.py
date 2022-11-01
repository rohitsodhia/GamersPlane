from rest_framework import serializers

from forums.models import Thread, Post


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
