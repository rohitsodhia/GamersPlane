import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";

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

export const createPost = async (data: {
	thread_id: number;
	title: string;
	body: JSONContent;
}): Promise<{ id: number }> => {
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
