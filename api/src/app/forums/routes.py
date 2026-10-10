from fastapi import APIRouter, status

from app.database import DBSessionDependency
from app.exceptions import ForbiddenException, NotFoundException
from app.forums import schemas
from app.forums.functions import (
    build_forum_tree,
    build_moderated_tree,
    get_heritage,
    is_game_root_forum,
    prune_unreadable,
)
from app.forums.permissions import ForumPermissions, Verbs, moderated_roots
from app.helpers.decorators import public
from app.middleware import Principal
from app.models import Forum
from app.posts.functions import can_post_as
from app.repositories import (
    CharacterRepository,
    DeckRepository,
    ForumRepository,
    GameRepository,
    PlayerRepository,
    PostRepository,
    ReadTrackingRepository,
    ThreadRepository,
)
from app.repositories.forum_repository import PROTECTED_FORUM_IDS, SITE_ROOT_FORUM_ID
from app.repositories.game_repository import GAMES_ROOT_FORUM_ID

forums = APIRouter(prefix="/forums")


def build_heritage_data(
    heritage_forums: list[Forum], permissions: ForumPermissions
) -> list[schemas.HeritageForumData]:
    return [
        schemas.HeritageForumData(
            id=heritage_forum.id,
            title=heritage_forum.title,
            moderate=permissions.has(heritage_forum, Verbs.FORUM_MODERATE),
        )
        for heritage_forum in heritage_forums
    ]


async def get_forum_or_404(forum_repository: ForumRepository, forum_id: int) -> Forum:
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    return forum


@forums.get("/moderated", response_model=list[schemas.ModeratedForumData])
async def get_moderated_forums(db_session: DBSessionDependency, principal: Principal):
    """The forums the principal moderates, nested under their ancestors.

    Game forums are only listed for games where the principal moderates one of
    the game's forums directly, so site-wide moderators don't get every game.
    """
    roots = await moderated_roots(db_session, principal)
    if not roots:
        return []

    forum_repository = ForumRepository(db_session, principal=principal)
    subtrees = list(
        await forum_repository.get_subtrees(
            [root.id for root in roots],
            only_game_ids={root.game_id for root in roots if root.game_id is not None},
        )
    )
    permissions = await ForumPermissions.load(db_session, principal, subtrees)
    moderated = [
        forum for forum in subtrees if permissions.has(forum, Verbs.FORUM_MODERATE)
    ]

    heading_ids = {forum_id for forum in moderated for forum_id in forum.heritage} - {
        forum.id for forum in subtrees
    }
    headings = (
        list(await forum_repository.get_multiple(list(heading_ids)))
        if heading_ids
        else []
    )

    return build_moderated_tree(
        [*subtrees, *headings], {forum.id for forum in moderated}
    )


@forums.get(
    "/{forum_id}/breadcrumbs", response_model=schemas.GetForumBreadcrumbsResponse
)
@public
async def get_forum_breadcrumbs(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")
    heritage_forums = await get_heritage(forum_repository, forum.heritage)
    permissions = await ForumPermissions.load(
        db_session, principal, [forum, *heritage_forums]
    )
    if not permissions.has(forum, Verbs.FORUM_READ):
        raise NotFoundException("Forum not found")

    return schemas.GetForumBreadcrumbsResponse(
        id=forum.id,
        title=forum.title,
        heritage=build_heritage_data(heritage_forums, permissions),
    )


@forums.get("/{forum_id}/decks", response_model=schemas.GetForumDecksResponse)
async def get_forum_decks(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    """The decks the principal could draw from when posting in this forum: all
    of the game's decks for its GM, else those that list them. Empty outside
    game forums or without ``forum_add_draws``."""
    forum = await get_forum_or_404(
        ForumRepository(db_session, principal=principal), forum_id
    )
    permissions = await ForumPermissions.require_read(
        db_session, principal, forum, "Forum not found"
    )
    if forum.game_id is None or not permissions.has(forum, Verbs.FORUM_ADD_DRAWS):
        return schemas.GetForumDecksResponse(decks=[])

    is_gm = await PlayerRepository(db_session, principal=principal).is_gm(
        forum.game_id, principal.id
    )
    decks = await DeckRepository(db_session, principal=principal).get_all_for_game(
        forum.game_id
    )
    return schemas.GetForumDecksResponse(
        decks=[
            schemas.DrawableDeck(
                id=deck.id,
                label=deck.label,
                type=deck.type_id,
                remaining=len(deck.order) - deck.position,
            )
            for deck in decks
            if is_gm or any(p.user_id == principal.id for p in deck.permissions)
        ]
    )


@forums.get("/{forum_id}/characters", response_model=schemas.GetForumCharactersResponse)
async def get_forum_characters(
    forum_id: int,
    db_session: DBSessionDependency,
    principal: Principal,
    thread_id: int | None = None,
):
    """The characters the principal could post as in this forum: their own
    approved, named ones in its game, plus everyone's for the game's GM. Empty
    outside game forums or without the right to post.

    ``default_id`` is the one they last used in ``thread_id``, if still on offer.
    """
    forum = await get_forum_or_404(
        ForumRepository(db_session, principal=principal), forum_id
    )
    permissions = await ForumPermissions.require_read(
        db_session, principal, forum, "Forum not found"
    )
    if forum.game_id is None or not (
        permissions.has(forum, Verbs.FORUM_MODERATE)
        or permissions.has(forum, Verbs.FORUM_WRITE)
    ):
        return schemas.GetForumCharactersResponse(characters=[])

    is_gm = await PlayerRepository(db_session, principal=principal).is_gm(
        forum.game_id, principal.id
    )
    candidates = await CharacterRepository(
        db_session, principal=principal
    ).get_approved_in_game(forum.game_id)
    options = sorted(
        (c for c in candidates if can_post_as(c, forum, principal, is_gm)),
        key=lambda c: (c.user_id != principal.id, c.name.strip().casefold(), c.id),
    )

    default_id = None
    if thread_id is not None:
        thread = await ThreadRepository(db_session, principal=principal).get(thread_id)
        if thread is not None and thread.forum_id == forum.id:
            last = await PostRepository(
                db_session, principal=principal
            ).get_latest_by_author(thread.id, principal.id)
            if last is not None and last.posted_as_id in {c.id for c in options}:
                default_id = last.posted_as_id

    return schemas.GetForumCharactersResponse(
        characters=[
            schemas.PostAsCharacter(
                id=character.id,
                name=character.name.strip(),
                owner=schemas.PostAsOwner(
                    id=character.user.id, username=character.user.username
                ),
            )
            for character in options
        ],
        default_id=default_id,
    )


@forums.get("/{forum_id}")
@public
async def get_forum(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await forum_repository.get(forum_id)
    if forum is None:
        raise NotFoundException("Forum not found")

    heritage_forums = await get_heritage(forum_repository, forum.heritage)

    # The games forum holds every game's forum; listing it (or the index above
    # it) shows only the games the user plays in or has favorited.
    only_game_ids = None
    if forum_id in (0, GAMES_ROOT_FORUM_ID):
        only_game_ids = (
            await GameRepository(
                db_session, principal=principal
            ).get_forum_listed_game_ids(principal.id)
            if principal
            else set()
        )
    descendants = list(
        await forum_repository.get_descendants(forum_id, only_game_ids=only_game_ids)
    )

    permissions = await ForumPermissions.load(
        db_session, principal, [forum, *descendants, *heritage_forums]
    )
    readable_ids = {
        candidate.id
        for candidate in descendants
        if permissions.has(candidate, Verbs.FORUM_READ)
    }
    descendants = prune_unreadable(descendants, forum_id, readable_ids)
    forum_permissions = permissions.allowed(forum)
    if Verbs.FORUM_READ not in forum_permissions and not descendants:
        raise NotFoundException("Forum not found")

    thread_repository = ThreadRepository(db_session, principal=principal)
    last_posts_by_forum_id = await thread_repository.get_last_posts_by_forum_ids(
        list(readable_ids)
    )

    # The forum itself joins the set only when readable, so a heading forum
    # never reports threads the principal can't see.
    unread_ids: set[int] = set()
    if principal:
        unread_candidates = set(readable_ids)
        if Verbs.FORUM_READ in forum_permissions:
            unread_candidates.add(forum.id)
        unread_ids = await ReadTrackingRepository(
            db_session, principal=principal
        ).unread_forum_ids(unread_candidates)

    children_forums_data = build_forum_tree(
        descendants, forum_id, last_posts_by_forum_id, readable_ids, unread_ids
    )

    return schemas.GetForum(
        id=forum.id,
        title=forum.title,
        description=forum.description,
        forum_type=forum.forum_type,
        parent_id=forum.parent_id,
        heritage=build_heritage_data(heritage_forums, permissions),
        order=forum.order,
        game_id=forum.game_id,
        thread_count=forum.thread_count if Verbs.FORUM_READ in forum_permissions else 0,
        has_unread=forum.id in unread_ids,
        permissions=sorted(verb.value for verb in forum_permissions),
        children=children_forums_data,
    )


@forums.post("/{forum_id}/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_forum_read(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    """Mark the forum and everything under it read. Visible on the same terms
    as ``get_forum``: the forum is readable, or leads to a readable subforum
    (so "mark all read" works from the index, forum 0)."""
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await get_forum_or_404(forum_repository, forum_id)
    descendants = list(await forum_repository.get_descendants(forum_id))
    permissions = await ForumPermissions.load(
        db_session, principal, [forum, *descendants]
    )
    if not permissions.has(forum, Verbs.FORUM_READ) and not any(
        permissions.has(descendant, Verbs.FORUM_READ) for descendant in descendants
    ):
        raise NotFoundException("Forum not found")

    await ReadTrackingRepository(db_session, principal=principal).mark_forum_read(forum)


@forums.patch("/{forum_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_forum(
    forum_id: int,
    data: schemas.UpdateForumInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await get_forum_or_404(forum_repository, forum_id)
    await ForumPermissions.require_moderate(db_session, principal, forum)

    if forum.id == SITE_ROOT_FORUM_ID:
        raise ForbiddenException("The forum index can't be edited")
    if is_game_root_forum(forum):
        raise ForbiddenException("A game's forum follows the game's details")
    if (
        data.title is not None
        and data.title != forum.title
        and forum.id in PROTECTED_FORUM_IDS
    ):
        raise ForbiddenException("This forum can't be renamed")

    await forum_repository.update(forum, title=data.title, description=data.description)


@forums.post("/{forum_id}/subforums", response_model=schemas.ForumIdResponse)
async def create_subforum(
    forum_id: int,
    data: schemas.CreateSubforumInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    parent = await get_forum_or_404(forum_repository, forum_id)
    await ForumPermissions.require_moderate(db_session, principal, parent)

    forum = await forum_repository.add(
        title=data.title,
        description=data.description or None,
        forum_type=data.forum_type,
        parent_id=parent.id,
        game_id=parent.game_id,
    )
    return schemas.ForumIdResponse(id=forum.id)


@forums.put("/{forum_id}/subforums/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_subforums(
    forum_id: int,
    data: schemas.ReorderSubforumsInput,
    db_session: DBSessionDependency,
    principal: Principal,
):
    forum_repository = ForumRepository(db_session, principal=principal)
    parent = await get_forum_or_404(forum_repository, forum_id)
    await ForumPermissions.require_moderate(db_session, principal, parent)

    await forum_repository.reorder_children(parent.id, data.forum_ids)


@forums.delete("/{forum_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_forum(
    forum_id: int, db_session: DBSessionDependency, principal: Principal
):
    """Deleting a forum is managing its parent's subforums, so it takes
    moderation of the parent."""
    forum_repository = ForumRepository(db_session, principal=principal)
    forum = await get_forum_or_404(forum_repository, forum_id)
    if forum.id in PROTECTED_FORUM_IDS:
        raise ForbiddenException("This forum can't be deleted")
    parent = await get_forum_or_404(forum_repository, forum.parent_id)
    await ForumPermissions.require_moderate(db_session, principal, parent)
    if is_game_root_forum(forum):
        raise ForbiddenException("A game's forum is deleted with the game")

    await forum_repository.delete(forum)
