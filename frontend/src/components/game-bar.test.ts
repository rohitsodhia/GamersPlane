import { describe, expect, it } from "vitest";
import type { GamePlayer, GamePlayerCharacter } from "#/queries/game";
import { approvedCharacterGroups, canReadGameForum } from "./game-bar";

const character = (
	id: number,
	overrides: Partial<GamePlayerCharacter> = {},
): GamePlayerCharacter => ({
	id,
	label: `Char ${id}`,
	type: "pc",
	approved: true,
	can_view: true,
	...overrides,
});

const player = (id: number, overrides: Partial<GamePlayer> = {}): GamePlayer => ({
	id,
	username: `user${id}`,
	is_gm: false,
	state: "accepted",
	characters: [character(id * 10)],
	...overrides,
});

describe("approvedCharacterGroups", () => {
	it("puts the viewer's group first and keeps the API order for the rest", () => {
		const groups = approvedCharacterGroups([player(1), player(2), player(3)], 2);

		expect(groups.map((g) => g.player.id)).toEqual([2, 1, 3]);
		expect(groups.map((g) => g.isViewer)).toEqual([true, false, false]);
	});

	it("leaves out pending characters, unaccepted players and empty groups", () => {
		const groups = approvedCharacterGroups(
			[
				player(1, {
					characters: [character(11), character(12, { approved: false })],
				}),
				player(2, { state: "invited" }),
				player(3, { characters: [character(31, { approved: false })] }),
				player(4, { characters: [] }),
			],
			null,
		);

		expect(groups.map((g) => g.player.id)).toEqual([1]);
		expect(groups[0].characters.map((c) => c.id)).toEqual([11]);
	});
});

describe("canReadGameForum", () => {
	it.each([
		{ public: true, viewer_state: null, expected: true },
		{ public: false, viewer_state: "accepted" as const, expected: true },
		{ public: false, viewer_state: "applied" as const, expected: false },
		{ public: false, viewer_state: null, expected: false },
	])("public=$public viewer_state=$viewer_state is $expected", (game) => {
		expect(canReadGameForum(game)).toBe(game.expected);
	});
});
