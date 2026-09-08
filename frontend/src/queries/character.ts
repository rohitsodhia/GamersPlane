import { ApiError, apiFetch } from "#/lib/api";

export type CharacterType = "pc" | "npc";

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
