import { ApiError, apiFetch } from "#/lib/api";

export type NewCharacterSheetInput = {
	name: string;
	system_id: string;
};

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
