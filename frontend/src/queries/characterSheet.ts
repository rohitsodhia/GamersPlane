import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";
import type { SheetSchema } from "#/routes/characters/sheets/-components/types";

export type NewCharacterSheetInput = {
	name: string;
	system_id: string;
};

export type CharacterSheetStatus = "private" | "public" | "official" | "retired";

export type CharacterSheet = {
	id: number;
	creator: { id: number; username: string; avatar: string };
	root_id: number | null;
	name: string;
	system: { id: string; name: string };
	layout: SheetSchema;
	status: CharacterSheetStatus;
};

export const characterSheetQueryOptions = (sheetId: number) =>
	queryOptions({
		queryKey: ["characterSheet", sheetId],
		queryFn: async (): Promise<CharacterSheet> => {
			const res = await apiFetch(`/character_sheets/${sheetId}`);
			if (!res.ok) {
				const { errors } = await res.json();
				throw new ApiError(res.status, errors);
			}
			return res.json();
		},
	});

export const createCharacterSheet = async (
	data: NewCharacterSheetInput,
): Promise<{ id: number }> => {
	const res = await apiFetch("/character_sheets/", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const updateCharacterSheet = async (
	sheetId: number,
	layout: SheetSchema,
): Promise<CharacterSheet> => {
	const res = await apiFetch(`/character_sheets/${sheetId}`, {
		method: "PATCH",
		body: JSON.stringify({ layout }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
