import { notFound, redirect } from "@tanstack/react-router";
import { ApiError } from "#/lib/api";

/**
 * Loader guard for a record loaded by id from the URL: rethrows an API 404 as
 * TanStack's `notFound()` so the route renders the site's 404 page (and SSR
 * serializes it properly). Every other error, including other `ApiError`s,
 * passes through unchanged. Composes with `redirectToLoginOnAuthFailure` in
 * either order.
 */
export function notFoundOnMissing<T>(promise: Promise<T>): Promise<T> {
	return promise.catch((error) => {
		if (error instanceof ApiError && error.status === 404) {
			throw notFound();
		}
		throw error;
	});
}

/**
 * Loader guard for a record the API decides who may see: rethrows an API 403
 * as a redirect to the site's 403 page. Wrap it around
 * `redirectToLoginOnAuthFailure`, so a 403 from a missing login still goes to
 * the login page first.
 */
export function forbiddenOnDenied<T>(promise: Promise<T>): Promise<T> {
	return promise.catch((error) => {
		if (error instanceof ApiError && error.status === 403) {
			throw redirect({ to: "/403", replace: true });
		}
		throw error;
	});
}

/** `beforeLoad` guard: ids in the URL must be positive integers. */
export function requirePositiveId(id: number) {
	if (!Number.isInteger(id) || id < 1) throw notFound();
}
