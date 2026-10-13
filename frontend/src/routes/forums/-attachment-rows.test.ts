import { describe, expect, it } from "vitest";
import type { DrawableDeck } from "#/queries/forums";
import { MAX_ROLLS_PER_POST } from "#/queries/posts";
import {
	type AttachmentAccess,
	addSheetRoll,
	attachmentAccess,
	attachmentErrors,
	availableDecks,
	buildAttachmentPayload,
	type DrawRow,
	newDrawRow,
	newRollRow,
	type RollRow,
	rollsBlockedReason,
} from "./-attachment-rows";

const decks: DrawableDeck[] = [
	{ id: 1, label: "Fate", type: "fate", remaining: 10 },
	{ id: 2, label: "Tarot", type: "tarot", remaining: 3 },
];
const everything: AttachmentAccess = { rolls: true, draws: true };

function drawRow(overrides: Partial<DrawRow> = {}): DrawRow {
	return { key: "d", deckId: 1, count: "1", reason: "Fortune", ...overrides };
}

describe("attachmentAccess", () => {
	const on = { allow_rolls: true, allow_draws: true };

	it("needs both the thread option and the permission", () => {
		expect(attachmentAccess(on, ["forum_add_rolls"])).toEqual({
			rolls: true,
			draws: false,
		});
		expect(
			attachmentAccess({ allow_rolls: false, allow_draws: true }, [
				"forum_add_rolls",
				"forum_add_draws",
			]),
		).toEqual({ rolls: false, draws: true });
	});

	it("lets moderators use whatever the thread allows", () => {
		expect(attachmentAccess(on, ["forum_moderate"])).toEqual(everything);
		expect(
			attachmentAccess({ allow_rolls: false, allow_draws: false }, ["forum_moderate"]),
		).toEqual({ rolls: false, draws: false });
	});
});

describe("availableDecks", () => {
	it("leaves out decks other rows picked but keeps the row's own", () => {
		const draws = [drawRow({ key: "a", deckId: 1 }), drawRow({ key: "b", deckId: 2 })];

		expect(availableDecks(decks, draws, "a").map((deck) => deck.id)).toEqual([1]);
		expect(availableDecks(decks, draws, null)).toEqual([]);
	});
});

describe("newDrawRow", () => {
	it("starts on the first unused deck, or none", () => {
		expect(newDrawRow(decks, [drawRow({ deckId: 1 })]).deckId).toBe(2);
		expect(
			newDrawRow(decks, [drawRow({ deckId: 1 }), drawRow({ deckId: 2 })]).deckId,
		).toBe(null);
	});
});

describe("attachmentErrors", () => {
	it("flags an empty roll", () => {
		const row = { ...newRollRow(), roll: "  " };

		expect(attachmentErrors({ rolls: [row], draws: [] }, everything, decks)).toEqual({
			[row.key]: "Enter what to roll.",
		});
	});

	it("flags a missing deck, a count outside what's left, and a blank reason", () => {
		const errors = attachmentErrors(
			{
				rolls: [],
				draws: [
					drawRow({ key: "none", deckId: null }),
					drawRow({ key: "over", deckId: 2, count: "4" }),
					drawRow({ key: "zero", count: "0" }),
					drawRow({ key: "fraction", count: "1.5" }),
					drawRow({ key: "empty", count: "" }),
					drawRow({ key: "blank", reason: " " }),
					drawRow({ key: "ok" }),
				],
			},
			everything,
			decks,
		);

		expect(Object.keys(errors).sort()).toEqual([
			"blank",
			"empty",
			"fraction",
			"none",
			"over",
			"zero",
		]);
		expect(errors["over"]).toBe("Draw between 1 and 3 cards.");
	});

	it("ignores rows the user can't send", () => {
		const row = newRollRow();

		expect(
			attachmentErrors(
				{ rolls: [row], draws: [drawRow({ reason: "" })] },
				{
					rolls: false,
					draws: false,
				},
				decks,
			),
		).toEqual({});
	});
});

describe("buildAttachmentPayload", () => {
	it("sends only the option each system reads", () => {
		const base = { ...newRollRow(), roll: " 4 ", reason: " Attack " };
		const { rolls } = buildAttachmentPayload(
			{
				rolls: [
					{ ...base, system: "basic", rerollAces: true, modifier: "3" },
					{ ...base, system: "fate", modifier: "-2", rerollAces: true },
					{ ...base, system: "fate", modifier: "" },
					{ ...base, system: "fengshui", rollType: "closed" },
					{ ...base, system: "starwarsffg", rerollAces: true },
				],
				draws: [],
			},
			everything,
		);

		expect(rolls.map((roll) => roll.options)).toEqual([
			{ reroll_aces: true },
			{ modifier: -2 },
			{ modifier: 0 },
			{ roll_type: "closed" },
			{},
		]);
		expect(rolls[0]).toMatchObject({ roll: "4", reason: "Attack" });
	});

	it("carries the hide flags and builds draws as numbers", () => {
		const payload = buildAttachmentPayload(
			{
				rolls: [{ ...newRollRow(), roll: "1d6", hideDice: true }],
				draws: [drawRow({ deckId: 2, count: "2", reason: " Omen " })],
			},
			everything,
		);

		expect(payload.rolls[0]).toMatchObject({
			hide_reason: false,
			hide_dice: true,
			hide_result: false,
		});
		expect(payload.draws).toEqual([{ deck_id: 2, count: 2, reason: "Omen" }]);
	});

	it("drops rolls or draws the user can't add, and draws with no deck", () => {
		const attachments = {
			rolls: [{ ...newRollRow(), roll: "1d6" }],
			draws: [drawRow(), drawRow({ key: "none", deckId: null })],
		};

		expect(
			buildAttachmentPayload(attachments, { rolls: false, draws: true }).rolls,
		).toEqual([]);
		expect(
			buildAttachmentPayload(attachments, { rolls: true, draws: false }).draws,
		).toEqual([]);
		expect(buildAttachmentPayload(attachments, everything).draws).toHaveLength(1);
	});
});

describe("addSheetRoll", () => {
	const roll = (dice: string, reason = "Athletics", mode: "new" | "add" = "new") => ({
		dice,
		reason,
		mode,
	});
	const rowWith = (overrides: Partial<RollRow>): RollRow => ({
		...newRollRow(),
		...overrides,
	});

	it("starts a new row for a `new` roll even when rows exist, with dice and reason prefilled", () => {
		const existing = rowWith({ roll: "1d6" });
		const added = addSheetRoll({ rolls: [existing], draws: [] }, roll("1d20"));
		if ("error" in added) throw new Error(added.error);

		expect(added.attachments.rolls.map((row) => row.roll)).toEqual(["1d6", "1d20"]);
		expect(added.rowKey).not.toBe(existing.key);
		expect(added.attachments.rolls[1]).toMatchObject({
			key: added.rowKey,
			system: "basic",
			roll: "1d20",
			reason: "Athletics",
		});
	});

	it("appends an `add` roll to the latest basic row as another comma group", () => {
		const first = rowWith({ roll: "1d6" });
		const last = rowWith({ roll: "2d6", reason: "Fireball" });
		const added = addSheetRoll(
			{ rolls: [first, last], draws: [] },
			roll("1d8", "Burn", "add"),
		);
		if ("error" in added) throw new Error(added.error);

		expect(added.rowKey).toBe(last.key);
		expect(added.attachments.rolls.map((row) => row.roll)).toEqual(["1d6", "2d6,1d8"]);
		// The row's own reason wins.
		expect(added.attachments.rolls[1]?.reason).toBe("Fireball");
	});

	it("fills an empty reason and an empty roll when appending", () => {
		const added = addSheetRoll(
			{ rolls: [rowWith({ roll: "  ", reason: " " })], draws: [] },
			roll("1d8", "Burn", "add"),
		);
		if ("error" in added) throw new Error(added.error);

		expect(added.attachments.rolls[0]).toMatchObject({ roll: "1d8", reason: "Burn" });
	});

	it("skips rows of another dice system when appending, starting a new row", () => {
		const fate = rowWith({ system: "fate", roll: "4" });
		const added = addSheetRoll(
			{ rolls: [fate], draws: [] },
			roll("1d8", "Burn", "add"),
		);
		if ("error" in added) throw new Error(added.error);

		expect(added.attachments.rolls).toHaveLength(2);
		expect(added.attachments.rolls[0]).toBe(fate);
	});

	it("refuses a new row when the post is full, but still appends to one", () => {
		const full = {
			rolls: Array.from({ length: MAX_ROLLS_PER_POST }, () => rowWith({ roll: "1d6" })),
			draws: [],
		};

		expect(addSheetRoll(full, roll("1d20"))).toEqual({
			error: `A post can have at most ${MAX_ROLLS_PER_POST} rolls.`,
		});
		const appended = addSheetRoll(full, roll("1d8", "Burn", "add"));
		expect("error" in appended).toBe(false);
	});
});

describe("rollsBlockedReason", () => {
	it("is null when the thread allows rolls and the user may add them", () => {
		expect(rollsBlockedReason({ allow_rolls: true }, ["forum_add_rolls"])).toBeNull();
		expect(rollsBlockedReason({ allow_rolls: true }, ["forum_moderate"])).toBeNull();
	});

	it("says rolls are off, with the caller's wording", () => {
		expect(rollsBlockedReason({ allow_rolls: false }, ["forum_add_rolls"])).toBe(
			"Rolls are turned off in this thread.",
		);
		expect(
			rollsBlockedReason({ allow_rolls: false }, ["forum_add_rolls"], "Off."),
		).toBe("Off.");
	});

	it("reports a missing permission before the thread option", () => {
		expect(rollsBlockedReason({ allow_rolls: false }, [])).toBe(
			"You can't add rolls in this forum.",
		);
	});
});
