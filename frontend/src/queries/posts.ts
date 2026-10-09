import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";
import type { DiceSystem, FengShuiRollType } from "#/queries/dice";

type Author = {
	id: number;
	username: string;
	avatar: string;
};

export type Post = {
	id: number;
	title: string;
	datestamp: string;
	author: Author;
	body: JSONContent;
};

export type PostDetails = Post & {
	is_first_post: boolean;
	thread_id: number;
	forum_id: number;
	page: number;
};

type PostsResponse = {
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

// Existing rolls and draws are never changed by an edit; these are added.
export const editPost = async (
	data: {
		post_id: number;
		title: string;
		body: JSONContent;
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
