import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";
import type { ScopeValues } from "#/routes/characters/sheets/-components/sheet-values";
import type { SheetSchema } from "#/routes/characters/sheets/-components/types";

export type CharacterType = "pc" | "npc";

export type Character = {
	id: number;
	label: string;
	name: string | null;
	type: CharacterType;
	values: ScopeValues | null;
	character_sheet: {
		id: number;
		name: string;
		creator: { id: number; username: string; avatar: string };
		system: { id: string; name: string };
		layout: SheetSchema;
	};
};

export const characterQueryOptions = (characterId: number) =>
	queryOptions({
		queryKey: ["character", characterId],
		queryFn: async (): Promise<Character> => {
			const res = await apiFetch(`/characters/${characterId}`);
			if (!res.ok) {
				const { errors } = await res.json();
				throw new ApiError(res.status, errors);
			}
			return res.json();
		},
	});

export const updateCharacter = async (
	characterId: number,
	values: ScopeValues,
): Promise<Character> => {
	const res = await apiFetch(`/characters/${characterId}`, {
		method: "PATCH",
		body: JSON.stringify({ values }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export type NewCharacterInput = {
	label: string;
	character_sheet_id: number;
	type: CharacterType;
};

export const createCharacter = async (
	data: NewCharacterInput,
): Promise<{ id: number }> => {
	const res = await apiFetch("/characters/", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
