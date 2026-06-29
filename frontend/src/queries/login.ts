import { ApiError, apiFetch } from "#/lib/api";

export const login = async (data: { identifier: string; password: string }) => {
	const res = await apiFetch("/auth/login", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
