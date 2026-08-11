import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

export type ThreadOption = "sticky" | "locked" | "allowRolls" | "allowDraws";

type Author = {
	id: number;
	name: string;
};

type Post = {
	id: number;
	title: string;
	datestamp: string;
	author: Author;
};

export type Thread = {
	id: number;
	title: string;
	first_post: Post;
	last_post: Post;
	options: ThreadOption[];
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
