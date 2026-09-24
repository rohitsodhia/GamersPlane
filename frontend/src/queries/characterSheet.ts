import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";
import type { SheetSchema } from "#/routes/characters/sheets/-components/types";

export type NewCharacterSheetInput = {
	name: string;
	system_id: string;
};

export type BasicCharacterSheet = {
	id: number;
	name: string;
	creator: { id: number; username: string };
	system: { id: string; name: string };
	description: string | null;
	favorited: boolean;
};

export const myCharacterSheetsQueryOptions = queryOptions({
	queryKey: ["characterSheets", "my"],
	queryFn: async (): Promise<BasicCharacterSheet[]> => {
		const res = await apiFetch("/character_sheets/my");
		if (!res.ok) {
			const { errors } = await res.json();
			throw new ApiError(res.status, errors);
		}
		return (await res.json()).char_sheets;
	},
});

export type GetMyCharacterSheetsResponse = {
	char_sheets: BasicCharacterSheet[];
	total: number;
	page: number;
};

export const myCharacterSheetsListQueryOptions = (
	params: { search?: string; system_id?: string; page?: number } = {},
) =>
	queryOptions({
		queryKey: ["characterSheets", "mine", params],
		queryFn: async (): Promise<GetMyCharacterSheetsResponse> => {
			const search = new URLSearchParams();
			if (params.search) search.set("search", params.search);
			if (params.system_id) search.set("system_id", params.system_id);
			if (params.page) search.set("page", String(params.page));
			const qs = search.toString();
			const res = await apiFetch(`/character_sheets/my${qs ? `?${qs}` : ""}`);
			if (!res.ok) {
				const { errors } = await res.json();
				throw new ApiError(res.status, errors);
			}
			return res.json();
		},
		placeholderData: keepPreviousData,
	});

export type CharacterSheetStatus = "private" | "public" | "official" | "retired";

export type CharacterSheet = {
	id: number;
	creator: { id: number; username: string };
	forked_from_id: number | null;
	name: string;
	system: { id: string; name: string };
	description: string | null;
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

export type LibraryCharacterSheet = {
	id: number;
	name: string;
	system: { id: string; name: string };
	creator: { id: number; username: string };
	description: string | null;
	status: CharacterSheetStatus;
	favorited: boolean;
};

export type GetCharacterSheetLibraryResponse = {
	char_sheets: LibraryCharacterSheet[];
	total: number;
	page: number;
};

export const characterSheetLibraryQueryOptions = (
	params: { search?: string; systems?: string[]; page?: number } = {},
) =>
	queryOptions({
		queryKey: ["characterSheets", "library", params],
		queryFn: async (): Promise<GetCharacterSheetLibraryResponse> => {
			const search = new URLSearchParams();
			if (params.search) search.set("search", params.search);
			for (const systemId of params.systems ?? []) search.append("systems", systemId);
			if (params.page) search.set("page", String(params.page));
			const qs = search.toString();
			const res = await apiFetch(`/character_sheets/library${qs ? `?${qs}` : ""}`);
			if (!res.ok) {
				const { errors } = await res.json();
				throw new ApiError(res.status, errors);
			}
			return res.json();
		},
		placeholderData: keepPreviousData,
	});

export const toggleCharacterSheetFavorite = async (
	sheetId: number,
): Promise<{ favorited: boolean }> => {
	const res = await apiFetch(`/character_sheets/${sheetId}/toggle_favorite`, {
		method: "PATCH",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const deleteCharacterSheet = async (sheetId: number): Promise<void> => {
	const res = await apiFetch(`/character_sheets/${sheetId}`, { method: "DELETE" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const updateCharacterSheet = async (
	sheetId: number,
	data: { name: string; description: string | null; layout: SheetSchema },
): Promise<CharacterSheet> => {
	const res = await apiFetch(`/character_sheets/${sheetId}`, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
