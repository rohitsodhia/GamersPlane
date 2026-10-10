import { describe, expect, it } from "vitest";
import type { PostableCharacter } from "#/queries/forums";
import {
	changedPostedAs,
	defaultPostAs,
	effectiveAvatarId,
	modeOf,
	orderCharacters,
	pickAvatar,
	selectOnOpen,
	showsFilter,
} from "./-post-as";

function character(
	id: number,
	overrides: Partial<PostableCharacter> = {},
): PostableCharacter {
	return {
		id,
		name: `Char ${id}`,
		owner: { id: 5, username: "bob" },
		type: "pc",
		avatars: [],
		last_used_at: null,
		...overrides,
	};
}

// Two avatars, the primary first.
const withAvatars = character(1, {
	avatars: [
		{ id: 10, url: "/a.png", is_primary: true },
		{ id: 11, url: "/b.png", is_primary: false },
	],
});
const ids = (list: PostableCharacter[]) => list.map((c) => c.id);

describe("defaultPostAs", () => {
	it("is the player without a default character", () => {
		expect(defaultPostAs({ default_id: null, default_avatar_id: 4 })).toEqual({
			characterId: null,
			avatarId: null,
		});
	});

	it("carries the default character and its avatar", () => {
		expect(defaultPostAs({ default_id: 3, default_avatar_id: 4 })).toEqual({
			characterId: 3,
			avatarId: 4,
		});
	});
});

describe("orderCharacters", () => {
	it("puts the five most recently used first, newest first, then the rest in order", () => {
		const list = [
			character(1),
			character(2, { last_used_at: "2026-01-01T00:00:00Z" }),
			character(3, { last_used_at: "2026-03-01T00:00:00Z" }),
			character(4),
			character(5, { last_used_at: "2026-02-01T00:00:00Z" }),
			character(6, { last_used_at: "2026-04-01T00:00:00Z" }),
			character(7, { last_used_at: "2026-05-01T00:00:00Z" }),
			character(8, { last_used_at: "2025-12-01T00:00:00Z" }),
		];
		const { items, recentCount } = orderCharacters(list);
		expect(recentCount).toBe(5);
		expect(ids(items)).toEqual([7, 6, 3, 5, 2, 1, 4, 8]);
	});

	it("has no recents when nothing was used", () => {
		const { items, recentCount } = orderCharacters([character(1), character(2)]);
		expect(recentCount).toBe(0);
		expect(ids(items)).toEqual([1, 2]);
	});

	it("filters by name or owner across both parts", () => {
		const list = [
			character(1, { name: "Aria" }),
			character(2, { name: "Brom", last_used_at: "2026-01-01T00:00:00Z" }),
			character(3, { name: "Cael", owner: { id: 6, username: "ARIANNA" } }),
			character(4, { name: "Dane" }),
		];
		const { items, recentCount } = orderCharacters(list, " aria ");
		expect(ids(items)).toEqual([1, 3]);
		expect(recentCount).toBe(0);
		// The recent character is filtered out too, so no divider is owed.
		expect(orderCharacters(list, "brom")).toMatchObject({ recentCount: 1 });
	});
});

describe("showsFilter", () => {
	it("appears only above eight characters", () => {
		const list = (n: number) => Array.from({ length: n }, (_, i) => character(i));
		expect(showsFilter(list(8))).toBe(false);
		expect(showsFilter(list(9))).toBe(true);
	});
});

describe("pickAvatar", () => {
	it("stores a non-primary avatar by id", () => {
		expect(pickAvatar(withAvatars, 11)).toEqual({ characterId: 1, avatarId: 11 });
	});

	it("stores the primary as null", () => {
		expect(pickAvatar(withAvatars, 10)).toEqual({ characterId: 1, avatarId: null });
	});
});

describe("effectiveAvatarId", () => {
	it("is the chosen avatar when it's still the character's", () => {
		expect(effectiveAvatarId(withAvatars, 11)).toBe(11);
	});

	it("falls back to the primary for null or a stale id", () => {
		expect(effectiveAvatarId(withAvatars, null)).toBe(10);
		expect(effectiveAvatarId(withAvatars, 99)).toBe(10);
	});

	it("is null for a character without avatars", () => {
		expect(effectiveAvatarId(character(2), null)).toBeNull();
	});

	it("passes the id through for an unlisted character", () => {
		expect(effectiveAvatarId(undefined, 7)).toBe(7);
	});
});

describe("modeOf", () => {
	const list = [character(1), character(2, { type: "npc" })];

	it("is player, or the selected character's type", () => {
		expect(modeOf({ characterId: null, avatarId: null }, list)).toBe("player");
		expect(modeOf({ characterId: 2, avatarId: null }, list)).toBe("npc");
	});

	it("is null for a character that isn't listed", () => {
		expect(modeOf({ characterId: 9, avatarId: null }, list)).toBeNull();
	});
});

describe("selectOnOpen", () => {
	const list = [
		character(1),
		character(2, { type: "npc" }),
		character(3, { type: "npc", last_used_at: "2026-01-01T00:00:00Z" }),
	];

	it("picks the first entry of the type, recents first, when none of it is chosen", () => {
		expect(selectOnOpen(list, "npc", { characterId: 1, avatarId: null })).toEqual({
			characterId: 3,
			avatarId: null,
		});
	});

	it("leaves a choice already in the type alone", () => {
		expect(selectOnOpen(list, "npc", { characterId: 2, avatarId: 5 })).toBeNull();
	});

	it("does nothing for a type with no characters", () => {
		expect(
			selectOnOpen([character(1)], "npc", { characterId: null, avatarId: null }),
		).toBeNull();
	});
});

describe("changedPostedAs", () => {
	const list = [withAvatars, character(2)];
	const player = { characterId: null, avatarId: null };

	it("omits everything when nothing moved", () => {
		expect(changedPostedAs(player, player, list)).toEqual({});
		// Initial avatar is the resolved primary id; current null is the same avatar.
		expect(
			changedPostedAs(
				{ characterId: 1, avatarId: 10 },
				{ characterId: 1, avatarId: null },
				list,
			),
		).toEqual({});
	});

	it("leaves an unlisted character alone", () => {
		expect(
			changedPostedAs(
				{ characterId: 9, avatarId: 7 },
				{ characterId: 9, avatarId: 7 },
				[],
			),
		).toEqual({});
	});

	it("sends null when switched back to the player", () => {
		expect(changedPostedAs({ characterId: 1, avatarId: 10 }, player, list)).toEqual({
			posted_as_id: null,
		});
	});

	it("sends only the character when its avatar is the primary", () => {
		expect(changedPostedAs(player, { characterId: 2, avatarId: null }, list)).toEqual({
			posted_as_id: 2,
		});
	});

	it("sends the avatar with a new character when it isn't the primary", () => {
		expect(changedPostedAs(player, { characterId: 1, avatarId: 11 }, list)).toEqual({
			posted_as_id: 1,
			posted_avatar_id: 11,
		});
	});

	it("sends just the avatar when only it changed", () => {
		const initial = { characterId: 1, avatarId: 10 };
		expect(changedPostedAs(initial, { characterId: 1, avatarId: 11 }, list)).toEqual({
			posted_avatar_id: 11,
		});
	});

	it("sends null to go back to the primary from another avatar", () => {
		const initial = { characterId: 1, avatarId: 11 };
		expect(changedPostedAs(initial, { characterId: 1, avatarId: null }, list)).toEqual({
			posted_avatar_id: null,
		});
	});
});
