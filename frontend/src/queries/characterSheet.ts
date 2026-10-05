import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
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
	description: JSONContent | null;
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
	description: JSONContent | null;
	version_id: number;
	// `null` for a draft: only publishing assigns a version number.
	version_number: number | null;
	// The newest published number (`null` before the first publish); a draft
	// publishes as this + 1.
	latest_version_number: number | null;
	changelog: JSONContent | null;
	// Only ever true for the sheet's creator: they're served their unpublished
	// draft when one exists, while everyone else gets the latest published version.
	is_draft: boolean;
	layout: SheetSchema;
	status: CharacterSheetStatus;
	// Only filled on a draft: fields in the latest published version the draft
	// no longer has. `label` is the field's value path, e.g. `abilities.str`.
	removed_fields: { id: string; label: string }[];
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

export type PublishedCharacterSheetVersion = {
	number: number;
	published_at: string;
	changelog: JSONContent | null;
};

// Published versions only, newest first.
export const characterSheetVersionsQueryOptions = (sheetId: number) =>
	queryOptions({
		queryKey: ["characterSheet", sheetId, "versions"],
		queryFn: async (): Promise<PublishedCharacterSheetVersion[]> => {
			const res = await apiFetch(`/character_sheets/${sheetId}/versions`);
			if (!res.ok) {
				const { errors } = await res.json();
				throw new ApiError(res.status, errors);
			}
			return (await res.json()).versions;
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

// Copies a published version (the latest unless `version` is given) into a new
// draft sheet owned by the caller.
export const copyCharacterSheet = async (
	sheetId: number,
	version?: number,
): Promise<{ id: number }> => {
	const qs = version === undefined ? "" : `?version=${version}`;
	const res = await apiFetch(`/character_sheets/${sheetId}/copy${qs}`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

// Undoes the creator's delete; the sheet comes back with its versions.
export const restoreCharacterSheet = async (sheetId: number): Promise<void> => {
	const res = await apiFetch(`/character_sheets/${sheetId}/restore`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export type LibraryCharacterSheet = {
	id: number;
	name: string;
	system: { id: string; name: string };
	creator: { id: number; username: string };
	description: JSONContent | null;
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
	data: {
		name: string;
		description: JSONContent | null;
		layout: SheetSchema;
		changelog: JSONContent | null;
	},
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

// Returns the latest published version, which the sheet falls back to.
export const discardCharacterSheetDraft = async (
	sheetId: number,
): Promise<CharacterSheet> => {
	const res = await apiFetch(`/character_sheets/${sheetId}/draft`, {
		method: "DELETE",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export type PublishCharacterSheetResponse = CharacterSheet & {
	// Field ids new to / missing from this version, relative to the previously
	// published one.
	added_field_ids: string[];
	removed_field_ids: string[];
};

export const publishCharacterSheet = async (
	sheetId: number,
): Promise<PublishCharacterSheetResponse> => {
	const res = await apiFetch(`/character_sheets/${sheetId}/publish`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
