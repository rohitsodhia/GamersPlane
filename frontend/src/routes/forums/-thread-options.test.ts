import { describe, expect, it } from "vitest";
import { changedThreadOptions, type ThreadOptionsValues } from "./-thread-options";

const initial: ThreadOptionsValues = {
	sticky: false,
	locked: false,
	allow_public_posting: false,
	allow_rolls: true,
	allow_draws: false,
	discord_webhook: "https://discord.example/hook",
};

describe("changedThreadOptions", () => {
	it("is undefined when nothing changed", () => {
		expect(changedThreadOptions(initial, { ...initial })).toBeUndefined();
	});

	it("includes only the booleans that changed", () => {
		expect(changedThreadOptions(initial, { ...initial, sticky: true })).toEqual({
			sticky: true,
		});
	});

	it("ignores whitespace-only webhook differences", () => {
		expect(
			changedThreadOptions(initial, {
				...initial,
				discord_webhook: `  ${initial.discord_webhook} `,
			}),
		).toBeUndefined();
	});

	it("sends the trimmed webhook when it changed", () => {
		expect(
			changedThreadOptions(initial, {
				...initial,
				discord_webhook: " https://discord.example/other ",
			}),
		).toEqual({ discord_webhook: "https://discord.example/other" });
	});

	it("sends an empty webhook to clear it", () => {
		expect(
			changedThreadOptions(initial, { ...initial, discord_webhook: "  " }),
		).toEqual({
			discord_webhook: "",
		});
	});
});
