import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";
import type { ScopeValues } from "#/routes/characters/sheets/-components/sheet-values";
import type { SheetSchema } from "#/routes/characters/sheets/-components/types";

export type CharacterType = "pc" | "npc";

export type CharacterAvatar = {
	id: number;
	url: string;
	is_primary: boolean;
};

export type Character = {
	id: number;
	label: string;
	name: string | null;
	type: CharacterType;
	values: ScopeValues | null;
	in_library: boolean;
	character_sheet: {
		id: number;
		name: string;
		creator: { id: number; username: string; avatar: string };
		system: { id: string; name: string };
		layout: SheetSchema;
	};
	avatars: CharacterAvatar[];
};

export type CharacterListItem = {
	id: number;
	label: string;
	type: CharacterType;
	in_library: boolean;
	character_sheet: { id: number; name: string; system: { id: string; name: string } };
};

export type GetCharactersResponse = {
	characters: CharacterListItem[];
	total: number;
	page: number;
};

export const myCharactersQueryOptions = (
	params: {
		search?: string;
		type?: CharacterType;
		system_id?: string;
		page?: number;
	} = {},
) =>
	queryOptions({
		queryKey: ["characters", "mine", params],
		queryFn: async (): Promise<GetCharactersResponse> => {
			const search = new URLSearchParams();
			if (params.search) search.set("search", params.search);
			if (params.type) search.set("type", params.type);
			if (params.system_id) search.set("system_id", params.system_id);
			if (params.page) search.set("page", String(params.page));
			const qs = search.toString();
			const res = await apiFetch(`/characters${qs ? `?${qs}` : ""}`);
			if (!res.ok) {
				const { errors } = await res.json();
				throw new ApiError(res.status, errors);
			}
			return res.json();
		},
		placeholderData: keepPreviousData,
	});

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
	data: { label?: string; type?: CharacterType; values?: ScopeValues },
): Promise<Character> => {
	const res = await apiFetch(`/characters/${characterId}`, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const toggleCharacterLibrary = async (characterId: number): Promise<void> => {
	const res = await apiFetch(`/characters/${characterId}/toggle_library`, {
		method: "PATCH",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const deleteCharacter = async (characterId: number): Promise<void> => {
	const res = await apiFetch(`/characters/${characterId}`, { method: "DELETE" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
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

export const addCharacterAvatar = async (
	characterId: number,
	avatar: File,
): Promise<{ success: boolean; avatar: CharacterAvatar }> => {
	const formData = new FormData();
	formData.append("avatar", avatar);

	const res = await apiFetch(`/characters/${characterId}/avatar`, {
		method: "POST",
		body: formData,
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const deleteCharacterAvatar = async (
	characterId: number,
	avatarId: number,
): Promise<{ success: boolean }> => {
	const res = await apiFetch(`/characters/${characterId}/avatar/${avatarId}`, {
		method: "DELETE",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const setPrimaryCharacterAvatar = async (
	characterId: number,
	avatarId: number,
): Promise<{ success: boolean; avatar: CharacterAvatar }> => {
	const res = await apiFetch(`/characters/${characterId}/avatar/${avatarId}`, {
		method: "PATCH",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
