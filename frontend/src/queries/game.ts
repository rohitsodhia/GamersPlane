import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";

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

export type NewGameInput = {
	title: string;
	system_id: string;
	allowed_char_sheets: string[];
	post_frequency: string;
	num_players: number;
	chars_per_player: number;
	description: JSONContent | null;
	char_gen_info: JSONContent | null;
	public: boolean;
	recruitment_thread_id: number | null;
	advanced_options: Record<string, unknown> | null;
};

export const createGame = async (data: NewGameInput): Promise<{ id: number }> => {
	const res = await apiFetch("/games/", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
