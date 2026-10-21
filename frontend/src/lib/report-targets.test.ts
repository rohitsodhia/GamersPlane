import { describe, expect, it } from "vitest";
import { describeReportTarget, reportTargetLink } from "./report-targets";

describe("describeReportTarget", () => {
	it("uses the title for posts and threads", () => {
		expect(describeReportTarget("post", { title: "Hello", body_text: "x" })).toBe(
			"Hello",
		);
	});

	it("falls back to a whitespace-collapsed body excerpt without a title", () => {
		expect(describeReportTarget("thread", { title: null, body_text: "a\n\n  b" })).toBe(
			"a b",
		);
	});

	it("truncates long bodies with an ellipsis", () => {
		const result = describeReportTarget("post", { body_text: "a".repeat(200) });
		expect(result).toBe(`${"a".repeat(80)}…`);
	});

	it("says there is no text when title and body are both missing", () => {
		expect(describeReportTarget("post", { title: " ", body_text: null })).toBe(
			"(no text)",
		);
	});

	it("describes users, characters and games by name", () => {
		expect(describeReportTarget("user", { username: "bob" })).toBe("bob");
		expect(describeReportTarget("character", { name: "Zed" })).toBe("Zed");
		expect(describeReportTarget("game", { title: "Dungeon" })).toBe("Dungeon");
	});

	it("labels image targets", () => {
		expect(describeReportTarget("user_avatar", { username: "bob" })).toBe(
			"Avatar of bob",
		);
		expect(describeReportTarget("game_background", { title: "Dungeon" })).toBe(
			"Background of Dungeon",
		);
		expect(describeReportTarget("npc_image", {})).toBe("Image");
	});
});

describe("reportTargetLink", () => {
	it("links a post to its thread with a post anchor", () => {
		expect(reportTargetLink("post", 7, { thread_id: 3 })).toEqual({
			to: "/forums/thread/$threadId",
			params: { threadId: 3 },
			hash: "post-7",
		});
	});

	it("has no link for a post whose snapshot lacks a thread", () => {
		expect(reportTargetLink("post", 7, {})).toBeNull();
	});

	it("links a thread by its own id", () => {
		expect(reportTargetLink("thread", 5, {})).toEqual({
			to: "/forums/thread/$threadId",
			params: { threadId: 5 },
		});
	});

	it("links user and user avatar reports to the user", () => {
		const expected = { to: "/user/$userId", params: { userId: 9 } };
		expect(reportTargetLink("user", 9, {})).toEqual(expected);
		expect(reportTargetLink("user_avatar", 9, {})).toEqual(expected);
	});

	it("links a character avatar to its character via the snapshot", () => {
		expect(reportTargetLink("character_avatar", 2, { character_id: 11 })).toEqual({
			to: "/characters/$characterId",
			params: { characterId: 11 },
		});
		expect(reportTargetLink("character_avatar", 2, {})).toBeNull();
	});

	it("links a game background to its game via the snapshot", () => {
		expect(reportTargetLink("game_background", 4, { game_id: 8 })).toEqual({
			to: "/games/$gameId",
			params: { gameId: 8 },
		});
	});

	it("falls back to the target id for a game background without a game_id", () => {
		expect(reportTargetLink("game_background", 4, {})).toEqual({
			to: "/games/$gameId",
			params: { gameId: 4 },
		});
	});

	it("has no page for NPC images", () => {
		expect(reportTargetLink("npc_image", 1, { game_id: 2 })).toBeNull();
	});
});
