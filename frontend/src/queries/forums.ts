import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

export type ForumType = "f" | "c";

export type HeritageForum = {
	id: number;
	title: string;
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
	children: ChildForum[];
};

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
	children: ChildForum[];
};

export type ForumBreadcrumbs = {
	id: number;
	title: string;
	heritage: HeritageForum[];
};

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
