import { ApiError, apiFetch } from "#/lib/api";

export const activate = async (token: string) => {
	const res = await apiFetch(`/auth/activate/${token}`, {
		method: "POST",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
