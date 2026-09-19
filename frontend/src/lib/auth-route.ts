import type { QueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";
import { ApiError } from "#/lib/api";
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

/**
 * Loader guard for data whose auth requirement isn't fixed by the route —
 * e.g. a resource that's sometimes public and sometimes only visible to its
 * owner. Wrap the loader's data-fetching promise in this: if it 403s AND we
 * don't currently hold a valid token, that means the resource needs a login
 * we don't have, so send the user to log in and back. If it 403s while we DO
 * hold a valid token, that's a real permission failure (wrong user, private
 * resource) that logging in again can't fix — let it surface as a normal
 * error instead of forcing the user out of their session.
 */
export function redirectToLoginOnAuthFailure<T>(
	promise: Promise<T>,
	location: { href: string },
): Promise<T> {
	return promise.catch((error) => {
		const { token, setToken } = useAuthStore.getState();
		if (error instanceof ApiError && error.status === 403 && !isTokenValid(token)) {
			setToken(null);
			throw redirect({
				to: "/login",
				search: { redirect: location.href },
			});
		}
		throw error;
	});
}
