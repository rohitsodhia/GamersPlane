import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

type SuggestedNumPlayers = {
	best: string;
	recommended: string;
};

export type LibraryGame = {
	id: number;
	name: string;
	thumbnail: string;
	image: string;
	min_players: number;
	max_players: number;
	suggested_num_players: SuggestedNumPlayers;
	min_play_time: number;
	max_play_time: number;
	suggested_age: number;
	complexity: number;
	suggested_tags: string[];
	dized: boolean;
	in_library: boolean;
	count: number;
};

export const GameQueryOptions = (gameId: number) =>
	queryOptions({
		queryKey: ["game", gameId],
		queryFn: async (): Promise<LibraryGame> => {
			const res = await apiFetch(`/games/${gameId}`);
			if (!res.ok) throw new Error("Failed to fetch game data");
			return res.json();
		},
		staleTime: 1000 * 60 * 5,
	});
