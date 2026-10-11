import { notFound } from "@tanstack/react-router";
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

/** `beforeLoad` guard: ids in the URL must be positive integers. */
export function requirePositiveId(id: number) {
	if (!Number.isInteger(id) || id < 1) throw notFound();
}
