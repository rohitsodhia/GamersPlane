import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";

export type GamePlayerState = "invited" | "applied" | "accepted";

export type GamePlayer = {
	id: number;
	username: string;
	is_gm: boolean;
	state: GamePlayerState;
};

export type GameDetails = {
	id: number;
	title: string;
	system: string;
	allowed_char_sheets: string[];
	gm: { id: number; username: string };
	created: string;
	end: string | null;
	post_frequency: { times_per: number; per_period: "d" | "w" };
	num_players: number;
	chars_per_player: number;
	description: JSONContent | null;
	char_gen_info: JSONContent | null;
	root_forum_id: number;
	status: "open" | "closed";
	public: boolean;
	recruitment_thread_id: number | null;
	advanced_options: Record<string, unknown> | null;
	retired: string | null;
	players: GamePlayer[];
	viewer_state: GamePlayerState | null;
	favorited: boolean;
};

export type Deck = {
	id: number;
	label: string;
	type: string;
	size: number;
	position: number;
	permissions: number[];
};

export type GameListItem = {
	id: number;
	title: string;
	system: string;
	gm: { id: number; username: string };
	post_frequency: { times_per: number; per_period: "d" | "w" };
	num_players: number;
	player_count: number;
	forum_id: number;
	is_gm: boolean;
	is_retired: boolean;
	status: "open" | "closed";
	favorited: boolean;
};

export const gamesQueryOptions = (params: { mine?: boolean } = {}) =>
	queryOptions({
		queryKey: ["games", params],
		queryFn: async (): Promise<GameListItem[]> => {
			const search = new URLSearchParams();
			if (params.mine) search.set("mine", "true");
			const qs = search.toString();
			const res = await apiFetch(`/games/${qs ? `?${qs}` : ""}`);
			if (!res.ok) throw new Error("Failed to fetch games");
			return (await res.json()).games;
		},
		staleTime: 1000 * 60,
	});

export const gameDetailsQueryOptions = (gameId: number) =>
	queryOptions({
		queryKey: ["game", gameId],
		queryFn: async (): Promise<GameDetails> => {
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

export const favoriteGame = async (gameId: number): Promise<{ favorite: boolean }> => {
	const res = await apiFetch(`/games/${gameId}/favorite`, { method: "POST" });
	if (!res.ok) throw new Error("Failed to favorite game");
	return res.json();
};

export const invitePlayer = async (gameId: number, username: string): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/invite`, {
		method: "POST",
		body: JSON.stringify({ username }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const toggleGameFlag = async (
	gameId: number,
	key: "status" | "public",
): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/toggle/${key}`, { method: "PATCH" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const toggleRetireGame = async (gameId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/retire`, { method: "PATCH" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const applyToGame = async (gameId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/apply`, { method: "POST" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const acceptInvite = async (gameId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/accept_invite`, { method: "POST" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const approvePlayer = async (gameId: number, userId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/player/${userId}/approve`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const toggleGm = async (gameId: number, userId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/player/${userId}/toggle_gm`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const deletePlayer = async (gameId: number, userId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/player/${userId}`, {
		method: "DELETE",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
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

export type UpdateGameInput = NewGameInput;

export const updateGame = async (
	gameId: number,
	data: UpdateGameInput,
): Promise<{ id: number }> => {
	const res = await apiFetch(`/games/${gameId}`, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const decksQueryOptions = (gameId: number) =>
	queryOptions({
		queryKey: ["decks", gameId],
		queryFn: async (): Promise<Deck[]> => {
			const res = await apiFetch(`/games/${gameId}/decks`);
			if (!res.ok) throw new Error("Failed to fetch decks");
			return (await res.json()).decks;
		},
	});

export type DeckInput = {
	label: string;
	type: string;
	permissions: number[];
};

export const createDeck = async (
	gameId: number,
	data: DeckInput,
): Promise<{ id: number }> => {
	const res = await apiFetch(`/games/${gameId}/decks`, {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const updateDeck = async (
	gameId: number,
	deckId: number,
	data: DeckInput,
): Promise<{ id: number }> => {
	const res = await apiFetch(`/games/${gameId}/decks/${deckId}`, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const shuffleDeck = async (gameId: number, deckId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/decks/${deckId}/shuffle`, {
		method: "PATCH",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const deleteDeck = async (gameId: number, deckId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/decks/${deckId}`, {
		method: "DELETE",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};
