import { describe, expect, it } from "vitest";
import { pendingText } from "./notificationText";

describe("pendingText", () => {
	it("joins players and characters with 'and'", () => {
		expect(pendingText(2, 3, "Dungeon")).toBe(
			"2 players and 3 characters pending in Dungeon",
		);
	});

	it("uses singular forms for a count of one", () => {
		expect(pendingText(1, 1, "Dungeon")).toBe(
			"1 player and 1 character pending in Dungeon",
		);
	});

	it("omits a zero count and the 'and'", () => {
		expect(pendingText(0, 2, "Dungeon")).toBe("2 characters pending in Dungeon");
		expect(pendingText(1, 0, "Dungeon")).toBe("1 player pending in Dungeon");
	});
});
