import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";

export type ThreadOptions = {
	sticky: boolean;
	locked: boolean;
	allow_public_posting: boolean;
	allow_rolls: boolean;
	allow_draws: boolean;
	discord_webhook: string | null;
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
};

type ThreadsResponse = {
	threads: Thread[];
	count: number;
	page: number;
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

export const createThread = async (data: {
	forum_id: number;
	title: string;
	body: JSONContent;
	options?: Partial<ThreadOptions>;
}): Promise<{ id: number }> => {
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
