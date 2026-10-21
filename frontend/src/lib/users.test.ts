import { describe, expect, it } from "vitest";
import { hasCustomAvatar } from "./users";

describe("hasCustomAvatar", () => {
	it("is false for the default avatar, with or without a query string", () => {
		expect(hasCustomAvatar("https://example.com/avatars/avatar.png")).toBe(false);
		expect(hasCustomAvatar("/avatars/avatar.png?v=3")).toBe(false);
	});

	it("is true for an uploaded avatar", () => {
		expect(hasCustomAvatar("https://example.com/avatars/42.png")).toBe(true);
		// Only the file name counts, not a longer name that ends the same way.
		expect(hasCustomAvatar("/avatars/my-avatar.png")).toBe(true);
	});
});
