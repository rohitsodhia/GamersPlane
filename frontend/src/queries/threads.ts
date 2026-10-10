import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";
import type { ForumPermission } from "#/queries/forums";
import type { PostAttachmentsInput } from "#/queries/posts";

export type ThreadOptions = {
	sticky: boolean;
	locked: boolean;
	allow_public_posting: boolean;
	allow_rolls: boolean;
	allow_draws: boolean;
};

type Author = {
	id: number;
	username: string;
};

type Post = {
	id: number;
	title: string;
	datestamp: string;
	author: Author;
};

export type Thread = {
	id: number;
	first_post: Post;
	last_post: Post;
	options: ThreadOptions;
	post_count: number;
	has_unread: boolean;
};

type ThreadsResponse = {
	threads: Thread[];
	count: number;
	page: number;
};

export type ThreadDetails = {
	id: number;
	forum_id: number;
	title: string;
	options: ThreadOptions;
	first_post_id: number;
	// The user's permissions on the thread's forum.
	permissions: ForumPermission[];
	// Null for guests, or when the thread is fully read.
	first_unread_post_id: number | null;
	first_unread_page: number | null;
};

export function threadsQueryOptions(forumId: number, page = 1) {
	return queryOptions({
		queryKey: ["threads", forumId, page],
		queryFn: async (): Promise<ThreadsResponse> => {
			const res = await apiFetch(`/threads?forum_id=${forumId}&page=${page}`);
			if (!res.ok) throw new Error("Failed to fetch threads");
			return res.json();
		},
	});
}

export function threadQueryOptions(threadId: number) {
	return queryOptions({
		queryKey: ["threads", threadId, "details"],
		queryFn: async (): Promise<ThreadDetails> => {
			const res = await apiFetch(`/threads/${threadId}`);
			if (!res.ok) throw new Error("Failed to fetch thread");
			return res.json();
		},
	});
}

const threadAction = async (path: string, body?: unknown): Promise<void> => {
	const res = await apiFetch(path, {
		method: "POST",
		...(body === undefined ? {} : { body: JSON.stringify(body) }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

// postId is the last post shown on the page the user is viewing.
export const recordThreadRead = (threadId: number, postId: number) =>
	threadAction(`/threads/${threadId}/read`, { post_id: postId });

// Makes the newest post unread again.
export const markThreadUnread = (threadId: number) =>
	threadAction(`/threads/${threadId}/mark-unread`);

// Only the fields present change. The webhook is write-only; "" or null clears it.
export type ThreadOptionsUpdate = Partial<ThreadOptions> & {
	discord_webhook?: string | null;
};

export const updateThread = async (
	threadId: number,
	options: ThreadOptionsUpdate,
): Promise<ThreadOptions> => {
	const res = await apiFetch(`/threads/${threadId}`, {
		method: "PATCH",
		body: JSON.stringify({ options }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const createThread = async (
	data: {
		forum_id: number;
		title: string;
		body: JSONContent;
		// The webhook is write-only here; thread reads never return it.
		options?: Partial<ThreadOptions> & { discord_webhook?: string | null };
	} & PostAttachmentsInput,
): Promise<{ id: number }> => {
	const res = await apiFetch("/threads", {
		method: "POST",
		body: JSON.stringify({ options: {}, ...data }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
