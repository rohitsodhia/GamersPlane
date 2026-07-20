import { apiFetch } from "#/lib/api";

export const refreshToken = async (): Promise<string | null> => {
	const res = await apiFetch("/auth/refresh", { method: "POST" });
	if (!res.ok) return null;
	const { jwt } = await res.json();
	return jwt;
};
