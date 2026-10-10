import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";
import type { DiceSystem, FengShuiRollType, RollDiceResult } from "#/queries/dice";
import type { ThreadOptionsUpdate } from "#/queries/threads";

type Author = {
	id: number;
	username: string;
	avatar: string;
};

// What a viewer without the dice may see of a roll's outcome.
export type PostRollSummary =
	| { total: number }
	| {
			net_success: number;
			net_advantage: number;
			triumph: number;
			despair: number;
	  };

// A roll as the viewer may see it: null means withheld from them. The author and
// moderators get everything, with the flags saying what others can't see.
export type PostRoll = {
	id: number;
	type: DiceSystem;
	reason: string | null;
	input: string | null;
	options: Record<string, unknown> | null;
	result: RollDiceResult | null;
	summary: PostRollSummary | null;
	hide_reason: boolean;
	hide_dice: boolean;
	hide_result: boolean;
};

// Unrevealed cards are null unless the viewer is the post's author.
export type PostDraw = {
	id: number;
	deck_id: number | null;
	deck_label: string;
	deck_type: string;
	reason: string;
	cards: (number | null)[];
	revealed: boolean[];
};

export type Post = {
	id: number;
	title: string;
	datestamp: string;
	author: Author;
	body: JSONContent;
	rolls: PostRoll[];
	draws: PostDraw[];
};

export type PostDetails = Post & {
	is_first_post: boolean;
	// Only set for the author of the thread's first post.
	discord_webhook: string | null;
	thread_id: number;
	forum_id: number;
	page: number;
};

export type PostsResponse = {
	posts: Post[];
	count: number;
	page: number;
};

export function postsQueryOptions(threadId: number, page = 1) {
	return queryOptions({
		queryKey: ["posts", threadId, page],
		queryFn: async (): Promise<PostsResponse> => {
			const res = await apiFetch(`/posts?thread_id=${threadId}&page=${page}`);
			if (!res.ok) throw new Error("Failed to fetch posts");
			return res.json();
		},
	});
}

export function postQueryOptions(postId: number) {
	return queryOptions({
		queryKey: ["posts", postId, "details"],
		queryFn: async (): Promise<PostDetails> => {
			const res = await apiFetch(`/posts/${postId}`);
			if (!res.ok) throw new Error("Failed to fetch post");
			return res.json();
		},
	});
}

export const MAX_ROLLS_PER_POST = 10;
export const MAX_DRAWS_PER_POST = 10;

export type NewRollInput = {
	type: DiceSystem;
	roll: string;
	reason?: string;
	// Only the option the system reads is sent.
	options: { reroll_aces?: boolean; modifier?: number; roll_type?: FengShuiRollType };
	hide_reason: boolean;
	hide_dice: boolean;
	hide_result: boolean;
};

export type NewDrawInput = {
	deck_id: number;
	count: number;
	reason: string;
};

// Rolls happen, and cards are taken, when the post is saved.
export type PostAttachmentsInput = {
	rolls?: NewRollInput[];
	draws?: NewDrawInput[];
};

export const createPost = async (
	data: {
		thread_id: number;
		title: string;
		body: JSONContent;
	} & PostAttachmentsInput,
): Promise<{ id: number }> => {
	const res = await apiFetch("/posts", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const deletePost = async (postId: number): Promise<void> => {
	const res = await apiFetch(`/posts/${postId}`, { method: "DELETE" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export type RollVisibilityInput = {
	id: number;
	hide_reason: boolean;
	hide_dice: boolean;
	hide_result: boolean;
};

// Existing rolls and draws are never changed by an edit apart from their roll
// visibility; the new ones are added.
export const editPost = async (
	data: {
		post_id: number;
		title: string;
		body: JSONContent;
		roll_visibility?: RollVisibilityInput[];
		// A minor edit doesn't ping the thread's Discord webhook.
		minor_edit?: boolean;
		// Only for a thread's first post.
		thread_options?: ThreadOptionsUpdate;
	} & PostAttachmentsInput,
): Promise<{ id: number }> => {
	const { post_id, ...body } = data;
	const res = await apiFetch(`/posts/${post_id}`, {
		method: "PATCH",
		body: JSON.stringify(body),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

// Flips whether one drawn card is shown to everyone; returns the draw as its
// author sees it.
export const toggleDrawCard = async (
	postId: number,
	drawId: number,
	index: number,
): Promise<PostDraw> => {
	const res = await apiFetch(`/posts/${postId}/draws/${drawId}/cards/${index}/toggle`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

// Swaps an updated draw into a cached posts page. Cache entries under the same
// "posts" prefix that aren't a page of posts (a single post's details) pass through.
export function withUpdatedDraw(
	cached: PostsResponse | PostDetails | undefined,
	postId: number,
	draw: PostDraw,
): PostsResponse | PostDetails | undefined {
	if (!cached || !("posts" in cached)) return cached;
	return {
		...cached,
		posts: cached.posts.map((post) =>
			post.id === postId
				? { ...post, draws: post.draws.map((d) => (d.id === draw.id ? draw : d)) }
				: post,
		),
	};
}
