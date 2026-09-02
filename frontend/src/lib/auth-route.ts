import type { QueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";
import { isTokenValid } from "#/lib/jwt";
import { hasPermission, meQueryOptions } from "#/queries/me";
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

/**
 * Loader guard for ACP sub-routes: redirects home unless the current user holds
 * one of `verbs` as a global permission (`admin` satisfies any check). Assumes
 * the parent `/acp` route has already gated on ACP access itself.
 */
export function requireAcpPermission(...verbs: string[]) {
	return async ({ context }: { context: { queryClient: QueryClient } }) => {
		const me = await context.queryClient
			.ensureQueryData(meQueryOptions)
			.catch(() => null);
		if (!hasPermission(me, ...verbs)) {
			throw redirect({ to: "/" });
		}
	};
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
