import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

export type GamerSort = "name" | "newest" | "oldest";

export type Gamer = {
	id: number;
	username: string;
	avatar: string;
	online: boolean;
	lfg: boolean;
	lastActivity: string | null;
};

export type GamersResponse = {
	gamers: Gamer[];
	total: number;
};

// Fixed on the API side (GAMERS_PER_PAGE), independent of the shared pagination size.
export const GAMERS_PER_PAGE = 25;

export type GamersParams = {
	search?: string;
	lfg?: boolean;
	includeInactive?: boolean;
	sort?: GamerSort;
	page?: number;
};

export function gamersQueryOptions(params: GamersParams) {
	return queryOptions({
		queryKey: ["gamers", params],
		queryFn: async (): Promise<GamersResponse> => {
			const search = new URLSearchParams({ page: String(params.page ?? 1) });
			if (params.search) search.set("search", params.search);
			if (params.lfg) search.set("lfg", "true");
			if (params.includeInactive) search.set("include_inactive", "true");
			if (params.sort) search.set("sort", params.sort);
			const res = await apiFetch(`/gamers?${search}`);
			if (!res.ok) {
				const errors = await res
					.json()
					.then((body) => body.errors ?? [])
					.catch(() => []);
				throw new ApiError(res.status, errors);
			}
			return res.json();
		},
		placeholderData: keepPreviousData,
		staleTime: 1000 * 30,
	});
}
