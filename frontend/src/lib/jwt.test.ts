import { describe, expect, it } from "vitest";
import { isTokenExpiringSoon, isTokenValid } from "./jwt";

function makeToken(exp: number | undefined) {
	const header = btoa(JSON.stringify({ alg: "none" }));
	const payload = btoa(JSON.stringify(exp === undefined ? {} : { exp }));
	return `${header}.${payload}.signature`;
}

describe("isTokenValid", () => {
	it("returns true for a token that expires in the future", () => {
		const futureExp = Math.floor(Date.now() / 1000) + 60;
		expect(isTokenValid(makeToken(futureExp))).toBe(true);
	});

	it("returns false for a token that already expired", () => {
		const pastExp = Math.floor(Date.now() / 1000) - 60;
		expect(isTokenValid(makeToken(pastExp))).toBe(false);
	});

	it("returns false for a malformed token", () => {
		expect(isTokenValid("not-a-real-token")).toBe(false);
	});

	it("returns false when the payload has no exp", () => {
		expect(isTokenValid(makeToken(undefined))).toBe(false);
	});
});

describe("isTokenExpiringSoon", () => {
	it("returns true when expiry is within the given window", () => {
		const exp = Math.floor(Date.now() / 1000) + 30;
		expect(isTokenExpiringSoon(makeToken(exp), 60_000)).toBe(true);
	});

	it("returns false when expiry is well outside the given window", () => {
		const exp = Math.floor(Date.now() / 1000) + 3600;
		expect(isTokenExpiringSoon(makeToken(exp), 60_000)).toBe(false);
	});
});
