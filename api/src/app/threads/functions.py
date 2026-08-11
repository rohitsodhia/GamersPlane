from app.models import Post
from app.threads import schemas


def build_post_data(post: Post) -> schemas.PostData:
    return schemas.PostData(
        id=post.id,
        title=post.title,
        datestamp=str(post.created_at),
        author=schemas.AuthorData(id=post.author.id, username=post.author.username),
    )
