from enum import Enum
from typing import TYPE_CHECKING, List

from sqlalchemy import ARRAY, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from models import Forum, Game


class Forum(Base, SoftDeleteMixin, TimestampMixin):
    class ForumTypes(Enum):
        FORUM = "f", "Forum"
        CATEGORY = "c", "Category"

    __tablename__ = "forums"
    # indexes = [models.Index(fields=["parent"]), models.Index(fields=["heritage"])]

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text(), nullable=True)
    forum_type: Mapped[ForumTypes] = mapped_column(
        String(1),
        default=ForumTypes.FORUM,
        nullable=True,
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("forums.id"))
    parent: Mapped["Forum"] = relationship()
    heritage: Mapped[List[int]] = mapped_column(ARRAY(Integer()))
    order: Mapped[int]
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    game: Mapped["Game"] = relationship()
    thread_count: Mapped[int] = mapped_column(default=0)

    @property
    def children(self):
        children_ids = cache.get(
            generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id}), []
        )
        if children_ids:
            cache.touch(
                generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id})
            )
            children_objs: List[Forum] = get_objects_by_id(
                children_ids, Forum, CacheKeys.FORUM_DETAILS.value
            )
        else:
            children_objs = Forum.objects.filter(parent=self.id).order_by("order")
            cache.set(
                generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id}),
                [obj.id for obj in children_objs],
            )
        children = [obj for obj in children_objs]
        return children

    def save(self, *args, **kwargs):
        if not self.order:
            children_ids = cache.get(
                generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id}), []
            )
            if children_ids:
                num_children = len(children_ids)
                cache.touch(
                    generate_cache_id(CacheKeys.FORUM_CHILDREN.value, {"id": self.id})
                )
            else:
                children = Forum.objects.filter(parent=self.parent.id)
                children_ids = []
                if children.count():
                    children_ids = [child["id"] for child in children.values("id")]
                    cache.set(
                        generate_cache_id(
                            CacheKeys.FORUM_CHILDREN.value, {"id": self.id}
                        ),
                        children_ids,
                    )
                num_children = len(children_ids)
            self.order = num_children + 1
        super().save(*args, **kwargs)

    def generate_heritage(self) -> None:
        if self.id:
            self.heritage = self.parent.heritage + [self.id]
