import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

export const SEARCH_MAX_LENGTH = 200;

export type SnippetPart = {
	text: string;
	match: boolean;
};

export type SearchResult = {
	post_id: number;
	thread_id: number;
	title: string;
	published_at: string;
	author: { id: number; username: string };
	forum_id: number;
	forum_title: string;
	game_id: number | null;
	rank: number;
	snippet: SnippetPart[];
};

type SearchResponse = {
	results: SearchResult[];
	// Capped at 1000; see count_capped.
	count: number;
	count_capped: boolean;
	page: number;
};

export function searchPostsQueryOptions(q: string, gameId?: number, page = 1) {
	const query = q.trim();
	return queryOptions({
		queryKey: ["forums", "search", query, gameId ?? null, page],
		enabled: query.length > 0,
		queryFn: async (): Promise<SearchResponse> => {
			const params = new URLSearchParams({ q: query, page: String(page) });
			if (gameId !== undefined) params.set("game_id", String(gameId));
			const res = await apiFetch(`/forums/search?${params}`);
			if (!res.ok) {
				const body = await res.json().catch(() => null);
				throw new ApiError(res.status, body?.errors ?? []);
			}
			return res.json();
		},
	});
}

export const resultCountLabel = (count: number, capped: boolean) =>
	capped ? `${count}+ results` : `${count} ${count === 1 ? "result" : "results"}`;
