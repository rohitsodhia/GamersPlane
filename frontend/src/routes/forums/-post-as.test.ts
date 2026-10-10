import { describe, expect, it } from "vitest";
import type { PostableCharacter } from "#/queries/forums";
import { changedPostedAs, postAsId, postAsKey, postAsOptions } from "./-post-as";

const mine: PostableCharacter = {
	id: 1,
	name: "Aria",
	owner: { id: 5, username: "bob" },
};
const theirs: PostableCharacter = {
	id: 2,
	name: "Brom",
	owner: { id: 6, username: "sue" },
};

describe("postAsKey / postAsId", () => {
	it("round-trips a character id and the player", () => {
		expect(postAsId(postAsKey(7))).toBe(7);
		expect(postAsId(postAsKey(null))).toBeNull();
	});
});

describe("postAsOptions", () => {
	it("starts with Player", () => {
		expect(postAsOptions([], 5)).toEqual([{ key: "player", label: "Player" }]);
	});

	it("names other players' characters with their owner", () => {
		expect(postAsOptions([mine, theirs], 5).map((o) => o.label)).toEqual([
			"Player",
			"Aria",
			"Brom (sue)",
		]);
	});

	it("keeps a current character that is no longer listed", () => {
		const options = postAsOptions([mine], 5, { id: 9, name: "Gone" });
		expect(options.at(-1)).toEqual({ key: "9", label: "Gone" });
	});

	it("doesn't duplicate a current character that is listed", () => {
		const options = postAsOptions([mine], 5, { id: 1, name: "Aria" });
		expect(options.filter((o) => o.key === "1")).toHaveLength(1);
	});
});

describe("changedPostedAs", () => {
	it("omits the key when the selection is unchanged", () => {
		expect(changedPostedAs(3, 3)).toEqual({});
		expect(changedPostedAs(null, null)).toEqual({});
	});

	it("sends null when switched back to the player", () => {
		expect(changedPostedAs(3, null)).toEqual({ posted_as_id: null });
	});

	it("sends the id when a character is chosen", () => {
		expect(changedPostedAs(null, 4)).toEqual({ posted_as_id: 4 });
		expect(changedPostedAs(3, 4)).toEqual({ posted_as_id: 4 });
	});
});
