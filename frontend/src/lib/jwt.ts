function getTokenExpiry(token: string | null | undefined): number | null {
	const payload = token?.split(".")[1];
	if (!payload) return null;

	try {
		const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
		const { exp } = JSON.parse(atob(base64));
		return typeof exp === "number" ? exp * 1000 : null;
	} catch {
		return null;
	}
}

export function isTokenValid(token: string | null | undefined): boolean {
	const expiry = getTokenExpiry(token);
	return expiry !== null && Date.now() < expiry;
}

export function isTokenExpiringSoon(
	token: string | null | undefined,
	withinMs: number,
): boolean {
	const expiry = getTokenExpiry(token);
	return expiry !== null && expiry - Date.now() < withinMs;
}
