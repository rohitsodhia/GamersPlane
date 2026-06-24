import { useAuthStore } from "#/store/auth";

export async function apiFetch(path: string, options: RequestInit = {}) {
	const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
	const token = useAuthStore.getState().token;
	const { headers, ...restOptions } = options;

	const response = await fetch(`${apiBaseUrl}${path}`, {
		...restOptions,
		headers: {
			"Content-Type": "application/json",
			...(token ? { Authorization: `Bearer ${token}` } : {}),
			...(headers instanceof Headers
				? Object.fromEntries(headers.entries())
				: Array.isArray(headers)
					? Object.fromEntries(headers)
					: headers),
		},
	});

	return response;
}
