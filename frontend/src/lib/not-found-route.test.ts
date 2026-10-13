import { isNotFound } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";
import { ApiError } from "#/lib/api";
import { notFoundOnMissing, requirePositiveId } from "#/lib/not-found-route";

async function caught(promise: Promise<unknown>) {
	try {
		await promise;
	} catch (error) {
		return error;
	}
	throw new Error("expected rejection");
}

describe("notFoundOnMissing", () => {
	it("turns an ApiError 404 into notFound()", async () => {
		const error = await caught(
			notFoundOnMissing(Promise.reject(new ApiError(404, []))),
		);
		expect(isNotFound(error)).toBe(true);
	});

	it("rethrows other ApiErrors unchanged", async () => {
		const original = new ApiError(403, []);
		const error = await caught(notFoundOnMissing(Promise.reject(original)));
		expect(error).toBe(original);
	});

	it("rethrows non-ApiErrors unchanged", async () => {
		const original = new Error("boom");
		const error = await caught(notFoundOnMissing(Promise.reject(original)));
		expect(error).toBe(original);
	});
});

describe("requirePositiveId", () => {
	it("accepts a positive integer", () => {
		expect(() => requirePositiveId(3)).not.toThrow();
	});

	it.each([0, 1.5, Number.NaN])("throws notFound() for %s", (id) => {
		let thrown: unknown;
		try {
			requirePositiveId(id);
		} catch (error) {
			thrown = error;
		}
		expect(isNotFound(thrown)).toBe(true);
	});
});
