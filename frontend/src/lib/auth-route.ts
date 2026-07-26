import { redirect } from "@tanstack/react-router";
import { isTokenValid } from "#/lib/jwt";
import { useAuthStore } from "#/stores/auth";

export function requireAuth({ location }: { location: { href: string } }) {
	const { token, setToken } = useAuthStore.getState();
	if (!token || !isTokenValid(token)) {
		if (token) setToken(null);
		throw redirect({
			to: "/login",
			search: { redirect: location.href },
		});
	}
	return { token };
}

export function redirectToLoginOnAuthFailure<T>(
	promise: Promise<T>,
	location: { href: string },
): Promise<T> {
	return promise.catch(() => {
		useAuthStore.getState().setToken(null);
		throw redirect({
			to: "/login",
			search: { redirect: location.href },
		});
	});
}
