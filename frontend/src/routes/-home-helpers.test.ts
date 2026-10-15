import { describe, expect, it } from "vitest";
import { playersLabel } from "./-home-helpers";

describe("playersLabel", () => {
	it("shows the player count while there is room", () => {
		expect(playersLabel({ player_count: 2, num_players: 5 })).toBe("2/5 players");
	});

	it("is Full when the count reaches the cap", () => {
		expect(playersLabel({ player_count: 5, num_players: 5 })).toBe("Full");
	});

	it("is Full when the game is over capacity", () => {
		expect(playersLabel({ player_count: 7, num_players: 5 })).toBe("Full");
	});
});
