import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

export type DeckType = {
	short: string;
	name: string;
	deck_size: number;
};

export const deckTypesQueryOptions = queryOptions({
	queryKey: ["deckTypes"],
	queryFn: async (): Promise<DeckType[]> => {
		const res = await apiFetch("/deck_types/");
		if (!res.ok) throw new Error("Failed to fetch deck types");
		return (await res.json()).types;
	},
	staleTime: 1000 * 60 * 5,
});
