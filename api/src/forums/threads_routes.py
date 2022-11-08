from fastapi import APIRouter, status
from django.core.paginator import Paginator

from globals import g, PAGINATE_PER_PAGE
from common.functions import error_response

from forums.models import Thread, Post
from forums.serializers import ThreadSerializer, PostSerializer
from forums.functions import has_permission
from permissions.models.permission import ForumPermissions

threads = APIRouter(prefix="/threads")


@threads.get("/{thread_id}")
def get_forums(thread_id: int = 0):
    thread: Thread = Thread.objects.get(id=thread_id)

    read_permission = has_permission(
        ForumPermissions.READ,
        g.current_user.id,
        thread.forum,
        g.current_user.get_forum_permissions(),
    )
    if not read_permission:
        return error_response(status_code=status.HTTP_403_FORBIDDEN)

    serialized_thread = ThreadSerializer(thread)

    all_posts = Post.objects.filter(thread=thread).order_by("-createdAt")
    paginator = Paginator(all_posts, PAGINATE_PER_PAGE)
    serialized_posts = PostSerializer(paginator.get_page(1).object_list, many=True)

    return {"thread": serialized_thread.data, "posts": serialized_posts}
