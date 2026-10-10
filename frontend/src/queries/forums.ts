import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

export type ForumType = "f" | "c";

export const SITE_ROOT_FORUM_ID = 0;
export const GAMES_ROOT_FORUM_ID = 2;
// Mirrors PROTECTED_FORUM_IDS in the API's forum_repository.py: these can't be
// renamed or deleted.
export const PROTECTED_FORUM_IDS = [SITE_ROOT_FORUM_ID, 1, GAMES_ROOT_FORUM_ID, 3];

// A game's own forum: its title follows the game, and it's deleted with it.
export const isGameRootForum = (forum: {
	game_id?: number | null;
	parent_id: number | null;
}) => forum.game_id != null && forum.parent_id === GAMES_ROOT_FORUM_ID;

// The index has no details of its own, and a game's forum takes its details
// from the game.
export const hasEditableDetails = (forum: {
	id: number;
	game_id?: number | null;
	parent_id: number | null;
}) => forum.id !== SITE_ROOT_FORUM_ID && !isGameRootForum(forum);

export type HeritageForum = {
	id: number;
	title: string;
	moderate: boolean;
};

type LastPostAuthor = {
	id: number;
	username: string;
};

export type LastPost = {
	id: number;
	title: string;
	datestamp: string;
	author: LastPostAuthor;
};

export type ChildForum = {
	id: number;
	title: string;
	description: string | null;
	forum_type: ForumType;
	parent_id: number | null;
	order: number;
	thread_count: number;
	post_count: number;
	last_post: LastPost | null;
	has_unread: boolean;
	children: ChildForum[];
};

export type ForumPermission =
	| "forum_read"
	| "forum_write"
	| "forum_edit"
	| "forum_delete"
	| "forum_create_thread"
	| "forum_delete_thread"
	| "forum_add_poll"
	| "forum_add_rolls"
	| "forum_add_draws"
	| "forum_moderate";

export type Forum = {
	id: number;
	title: string;
	description: string | null;
	forum_type: ForumType;
	parent_id: number | null;
	heritage: HeritageForum[];
	order: number;
	game_id: number | null;
	thread_count: number;
	// Without forum_read the forum is only shown as a heading over subforums the
	// user can read, and has no threads to list.
	permissions: ForumPermission[];
	has_unread: boolean;
	children: ChildForum[];
};

export type ForumBreadcrumbs = {
	id: number;
	title: string;
	heritage: HeritageForum[];
};

export type ModeratedForum = {
	id: number;
	title: string;
	// False for a forum listed only as a heading over forums the user moderates.
	moderate: boolean;
	children: ModeratedForum[];
};

export const moderatedForumsQueryOptions = queryOptions({
	queryKey: ["forums", "moderated"],
	queryFn: async (): Promise<ModeratedForum[]> => {
		const res = await apiFetch("/forums/moderated");
		if (!res.ok) throw new Error("Failed to fetch moderated forums");
		return res.json();
	},
	staleTime: 1000 * 60,
});

export function forumQueryOptions(id: number) {
	return queryOptions({
		queryKey: ["forums", id],
		queryFn: async (): Promise<Forum> => {
			const res = await apiFetch(`/forums/${id}`);
			if (!res.ok) throw new Error("Failed to fetch forum");
			return res.json();
		},
		staleTime: 1000 * 60,
	});
}

export type DrawableDeck = {
	id: number;
	label: string;
	type: string;
	remaining: number;
};

// The decks the user can draw from when posting in the forum (empty outside game
// forums, or without forum_add_draws). Always refetched: draws change `remaining`.
export function forumDecksQueryOptions(id: number) {
	return queryOptions({
		queryKey: ["forums", id, "decks"],
		queryFn: async (): Promise<DrawableDeck[]> => {
			const res = await apiFetch(`/forums/${id}/decks`);
			if (!res.ok) throw new Error("Failed to fetch forum decks");
			return (await res.json()).decks;
		},
		staleTime: 0,
	});
}

export async function forumMutate(path: string, method: string, body?: unknown) {
	const res = await apiFetch(path, {
		method,
		...(body === undefined ? {} : { body: JSON.stringify(body) }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res;
}

// An empty description clears it.
export const updateForum = (
	forumId: number,
	body: { title?: string; description?: string },
) => forumMutate(`/forums/${forumId}`, "PATCH", body);

export const createSubforum = async (
	forumId: number,
	body: { title: string; description?: string; forum_type: ForumType },
): Promise<number> => {
	const res = await forumMutate(`/forums/${forumId}/subforums`, "POST", body);
	return (await res.json()).id;
};

// The listed subforums swap among the order slots they already hold.
export const reorderSubforums = (forumId: number, forumIds: number[]) =>
	forumMutate(`/forums/${forumId}/subforums/order`, "PUT", { forum_ids: forumIds });

// Marks the forum and every forum under it read. Forum 0 is the whole site.
export const markForumRead = (forumId: number) =>
	forumMutate(`/forums/${forumId}/mark-read`, "POST");

export const deleteForum = (forumId: number) =>
	forumMutate(`/forums/${forumId}`, "DELETE");

export function forumBreadcrumbsQueryOptions(id: number) {
	return queryOptions({
		queryKey: ["forums", id, "breadcrumbs"],
		queryFn: async (): Promise<ForumBreadcrumbs> => {
			const res = await apiFetch(`/forums/${id}/breadcrumbs`);
			if (!res.ok) throw new Error("Failed to fetch forum breadcrumbs");
			return res.json();
		},
		staleTime: 1000 * 60,
	});
}
