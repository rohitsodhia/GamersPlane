import { describe, expect, it } from "vitest";
import type { PostableCharacter } from "#/queries/forums";
import type { GameNpc } from "#/queries/game";
import {
	changedPostedAs,
	defaultPostAs,
	effectiveAvatarId,
	entriesOfType,
	isEntrySelected,
	modeOf,
	newNpcEntry,
	npcImageUrl,
	orderEntries,
	type PostAsValue,
	pickAvatar,
	pickEntry,
	postAsOfPost,
	postAsPayload,
	resolveNpc,
	selectOnOpen,
	showsFilter,
	visibleTypes,
	withNpcImage,
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

function npc(id: number, overrides: Partial<GameNpc> = {}): GameNpc {
	return { id, name: `Npc ${id}`, image: null, last_used_at: null, ...overrides };
}

// Two avatars, the primary first.
const withAvatars = character(1, {
	avatars: [
		{ id: 10, url: "/a.png", is_primary: true },
		{ id: 11, url: "/b.png", is_primary: false },
	],
});
const player: PostAsValue = { characterId: null, avatarId: null };
const npcOf = (
	id: number | null,
	name: string,
	imageId: number | null = null,
): PostAsValue => ({ characterId: null, avatarId: null, npc: { id, name, imageId } });
// The keys of a PC list as shown.
const pcKeys = (list: PostableCharacter[], query = "") =>
	orderEntries(entriesOfType(list, [], "pc"), query).items.map((e) => e.key);

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

	it("carries the default quick NPC, with its image", () => {
		const npcs = [npc(7, { name: "Guard", image: { id: 2, url: "/g.png" } })];
		expect(
			defaultPostAs({
				default_id: null,
				default_avatar_id: null,
				default_npc_id: 7,
				npcs,
			}),
		).toEqual(npcOf(7, "Guard", 2));
	});

	it("ignores a default quick NPC that isn't listed", () => {
		expect(
			defaultPostAs({
				default_id: 3,
				default_avatar_id: null,
				default_npc_id: 7,
				npcs: [],
			}),
		).toEqual({ characterId: 3, avatarId: null });
	});
});

describe("orderEntries", () => {
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
		const { items, recentCount } = orderEntries(entriesOfType(list, [], "pc"));
		expect(recentCount).toBe(5);
		expect(items.map((e) => e.key)).toEqual([
			"c7",
			"c6",
			"c3",
			"c5",
			"c2",
			"c1",
			"c4",
			"c8",
		]);
	});

	it("filters characters by name or owner across both parts", () => {
		const list = [
			character(1, { name: "Aria" }),
			character(2, { name: "Brom", last_used_at: "2026-01-01T00:00:00Z" }),
			character(3, { name: "Cael", owner: { id: 6, username: "ARIANNA" } }),
			character(4, { name: "Dane" }),
		];
		expect(pcKeys(list, " aria ")).toEqual(["c1", "c3"]);
		// The recent character is filtered out too, so no divider is owed.
		expect(orderEntries(entriesOfType(list, [], "pc"), "aria").recentCount).toBe(0);
		expect(orderEntries(entriesOfType(list, [], "pc"), "brom").recentCount).toBe(1);
	});

	it("ranks NPC characters and quick NPCs together by last use", () => {
		const characters = [
			character(1, { type: "npc", last_used_at: "2026-01-01T00:00:00Z" }),
			character(2, { type: "npc" }),
		];
		const npcs = [
			npc(1, { last_used_at: "2026-02-01T00:00:00Z" }),
			npc(2, { name: "Guard" }),
		];
		const { items, recentCount } = orderEntries(entriesOfType(characters, npcs, "npc"));
		expect(items.map((e) => e.key)).toEqual(["n1", "c1", "c2", "n2"]);
		expect(recentCount).toBe(2);
	});

	it("filters quick NPCs by name only", () => {
		const npcs = [npc(1, { name: "Guard" }), npc(2, { name: "Mayor" })];
		const entries = entriesOfType([], npcs, "npc");
		expect(orderEntries(entries, "gua").items.map((e) => e.key)).toEqual(["n1"]);
	});

	it("keeps quick NPCs out of the PC list", () => {
		expect(entriesOfType([character(1)], [npc(1)], "pc").map((e) => e.key)).toEqual([
			"c1",
		]);
	});
});

describe("newNpcEntry", () => {
	const npcs = [npc(1, { name: "Guard" })];

	it("offers the typed name, trimmed", () => {
		expect(newNpcEntry("  Mayor ", npcs, player)).toMatchObject({
			kind: "new",
			name: "Mayor",
		});
	});

	it("is hidden when a quick NPC has exactly that name", () => {
		expect(newNpcEntry("Guard", npcs, player)).toBeNull();
		// A partial match still lets a new one be made.
		expect(newNpcEntry("Guar", npcs, player)).toMatchObject({ name: "Guar" });
	});

	it("is hidden with nothing typed and nothing unsaved chosen", () => {
		expect(newNpcEntry("  ", npcs, player)).toBeNull();
		expect(newNpcEntry("", npcs, npcOf(1, "Guard"))).toBeNull();
	});

	it("keeps the row of an unsaved NPC already chosen", () => {
		expect(newNpcEntry("", npcs, npcOf(null, "Mayor"))).toMatchObject({
			name: "Mayor",
		});
	});
});

describe("showsFilter", () => {
	it("appears only above eight entries", () => {
		const list = (n: number) => Array.from({ length: n }, (_, i) => i);
		expect(showsFilter(list(8))).toBe(false);
		expect(showsFilter(list(9))).toBe(true);
	});

	it("always appears where a quick NPC can be named", () => {
		expect(showsFilter([], true)).toBe(true);
	});
});

describe("visibleTypes", () => {
	const types = (...args: Parameters<typeof visibleTypes>) =>
		visibleTypes(...args).map((t) => t.type);

	it("lists a type only when there is someone of it", () => {
		expect(types([character(1)], [], false)).toEqual(["pc"]);
		expect(types([character(1, { type: "npc" })], [], false)).toEqual(["npc"]);
		expect(types([], [], false)).toEqual([]);
	});

	it("shows NPC for quick NPCs alone", () => {
		expect(types([], [npc(1)], false)).toEqual(["npc"]);
	});

	it("shows NPC to a GM with nothing yet, but never PC", () => {
		expect(types([], [], true)).toEqual(["npc"]);
	});
});

describe("pickEntry and isEntrySelected", () => {
	it("picks a quick NPC with its image id", () => {
		const entry = entriesOfType(
			[],
			[npc(3, { name: "Guard", image: { id: 9, url: "/g" } })],
			"npc",
		)[0];
		expect(pickEntry(entry)).toEqual(npcOf(3, "Guard", 9));
	});

	it("picks a new quick NPC without an id or image", () => {
		const entry = newNpcEntry("Mayor", [], player);
		expect(entry && pickEntry(entry)).toEqual(npcOf(null, "Mayor", null));
	});

	it("tells which kind of row is chosen", () => {
		const [char, quick] = entriesOfType(
			[character(2, { type: "npc" })],
			[npc(3)],
			"npc",
		);
		const created = newNpcEntry("Mayor", [], player);
		expect(isEntrySelected(char, { characterId: 2, avatarId: null })).toBe(true);
		expect(isEntrySelected(char, npcOf(3, "Npc 3"))).toBe(false);
		expect(isEntrySelected(quick, npcOf(3, "Npc 3"))).toBe(true);
		expect(isEntrySelected(quick, { characterId: 2, avatarId: null })).toBe(false);
		expect(created && isEntrySelected(created, npcOf(null, "Mayor"))).toBe(true);
		// A saved pair of the same name is a different row.
		expect(created && isEntrySelected(created, npcOf(3, "Mayor"))).toBe(false);
	});
});

describe("resolveNpc", () => {
	const npcs = [npc(3, { name: "Guard", image: { id: 9, url: "/g" } })];

	it("fills in an existing pair's image id", () => {
		expect(resolveNpc({ id: 3, name: "Guard", imageId: null }, npcs)).toEqual({
			id: 3,
			name: "Guard",
			imageId: 9,
		});
	});

	it("gives a new pair the id the server has since made", () => {
		expect(resolveNpc({ id: null, name: "Guard", imageId: 9 }, npcs).id).toBe(3);
	});

	it("leaves an unlisted pair alone", () => {
		const unlisted = { id: 8, name: "Gone", imageId: null };
		expect(resolveNpc(unlisted, npcs)).toEqual(unlisted);
	});
});

describe("withNpcImage", () => {
	const npcs = [
		npc(1, { name: "Guard" }),
		npc(2, { name: "Guard", image: { id: 9, url: "/g" } }),
	];

	it("makes a different pair of the same name for another image", () => {
		expect(withNpcImage({ id: 1, name: "Guard", imageId: null }, 4, npcs)).toEqual(
			npcOf(null, "Guard", 4),
		);
	});

	it("reuses an existing pair that has that name and image", () => {
		expect(withNpcImage({ id: 1, name: "Guard", imageId: null }, 9, npcs)).toEqual(
			npcOf(2, "Guard", 9),
		);
	});

	it("keeps the pair when the image is the same", () => {
		expect(withNpcImage({ id: 1, name: "Guard", imageId: null }, null, npcs)).toEqual(
			npcOf(1, "Guard", null),
		);
	});
});

describe("npcImageUrl", () => {
	it("is null without an image", () => {
		expect(
			npcImageUrl({ id: 1, name: "A", imageId: null }, [{ id: 1, url: "/x" }], []),
		).toBeNull();
	});

	it("finds the image in the library, then the NPC list, then the post's NPC", () => {
		const target = { id: 1, name: "A", imageId: 5 };
		expect(npcImageUrl(target, [{ id: 5, url: "/lib" }], [])).toBe("/lib");
		expect(npcImageUrl(target, [], [npc(1, { image: { id: 5, url: "/npc" } })])).toBe(
			"/npc",
		);
		expect(npcImageUrl(target, [], [], { id: 1, image: "/post" })).toBe("/post");
		expect(npcImageUrl(target, [], [], { id: 2, image: "/post" })).toBeNull();
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
		expect(modeOf(player, list)).toBe("player");
		expect(modeOf({ characterId: 2, avatarId: null }, list)).toBe("npc");
	});

	it("is npc for a quick NPC", () => {
		expect(modeOf(npcOf(null, "Mayor"), list)).toBe("npc");
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
		expect(selectOnOpen(list, "npc", npcOf(null, "Mayor"))).toBeNull();
	});

	it("does nothing for a type with no entries", () => {
		expect(selectOnOpen([character(1)], "npc", player)).toBeNull();
	});

	it("picks the most recent across NPC characters and quick NPCs", () => {
		const npcs = [npc(7, { name: "Guard", last_used_at: "2026-02-01T00:00:00Z" })];
		expect(selectOnOpen(list, "npc", player, npcs)).toEqual(npcOf(7, "Guard", null));
	});

	it("moves off a quick NPC to open the PC list", () => {
		expect(selectOnOpen(list, "pc", npcOf(7, "Guard"))).toEqual({
			characterId: 1,
			avatarId: null,
		});
	});
});

describe("postAsPayload", () => {
	it("sends the character and avatar", () => {
		expect(postAsPayload({ characterId: 1, avatarId: 11 })).toEqual({
			posted_as_id: 1,
			posted_avatar_id: 11,
		});
	});

	it("sends only the quick NPC for one", () => {
		expect(postAsPayload(npcOf(7, "Guard", 9))).toEqual({
			posted_npc: { name: "Guard", image_id: 9 },
		});
	});
});

describe("postAsOfPost", () => {
	it("is the post's NPC, character or the user", () => {
		const base = { posted_as: null, posted_npc: null };
		expect(postAsOfPost(base)).toEqual(player);
		expect(postAsOfPost({ ...base, posted_as: { id: 1, avatar_id: 10 } })).toEqual({
			characterId: 1,
			avatarId: 10,
		});
		expect(postAsOfPost({ ...base, posted_npc: { id: 7, name: "Guard" } })).toEqual(
			npcOf(7, "Guard", null),
		);
	});
});

describe("changedPostedAs", () => {
	const list = [withAvatars, character(2)];

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

	describe("quick NPCs", () => {
		// A post's NPC doesn't know its image id.
		const posted = npcOf(7, "Guard", null);

		it("sends the NPC when switching to one", () => {
			expect(changedPostedAs(player, npcOf(null, "Mayor", 4), list)).toEqual({
				posted_npc: { name: "Mayor", image_id: 4 },
			});
			expect(changedPostedAs({ characterId: 1, avatarId: 10 }, posted, list)).toEqual({
				posted_npc: { name: "Guard", image_id: null },
			});
		});

		it("omits an unchanged NPC, told by id", () => {
			expect(changedPostedAs(posted, npcOf(7, "Guard", 9), list)).toEqual({});
		});

		it("omits an unchanged NPC that was never saved, told by name and image", () => {
			expect(
				changedPostedAs(npcOf(null, "Mayor", 4), npcOf(null, "Mayor", 4), list),
			).toEqual({});
		});

		it("sends the NPC when its image changed", () => {
			expect(changedPostedAs(posted, npcOf(null, "Guard", 4), list)).toEqual({
				posted_npc: { name: "Guard", image_id: 4 },
			});
		});

		it("sends null when switched back to the player", () => {
			expect(changedPostedAs(posted, player, list)).toEqual({ posted_npc: null });
		});

		it("clears the NPC and sets the character when switched to one", () => {
			expect(changedPostedAs(posted, { characterId: 2, avatarId: null }, list)).toEqual(
				{
					posted_npc: null,
					posted_as_id: 2,
				},
			);
			expect(changedPostedAs(posted, { characterId: 1, avatarId: 11 }, list)).toEqual({
				posted_npc: null,
				posted_as_id: 1,
				posted_avatar_id: 11,
			});
		});
	});
});
