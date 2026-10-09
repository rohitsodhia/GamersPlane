import { describe, expect, it } from "vitest";
import type { PostRoll } from "#/queries/posts";
import {
	changedRollVisibility,
	hiddenTag,
	initialVisibility,
	rollDisplay,
	rollParens,
	summaryText,
} from "./-post-rolls";

function roll(overrides: Partial<PostRoll> = {}): PostRoll {
	return {
		id: 1,
		type: "basic",
		reason: "Attack",
		input: "2d6",
		options: {},
		result: { groups: [], total: 7 },
		summary: null,
		hide_reason: false,
		hide_dice: false,
		hide_result: false,
		...overrides,
	};
}

describe("rollDisplay", () => {
	it("shows nothing as withheld or hidden for a plain roll", () => {
		const display = rollDisplay(roll());
		expect(display.reasonWithheld).toBe(false);
		expect(display.inputWithheld).toBe(false);
		expect(display.resultWithheld).toBe(false);
		expect(display.summaryOnly).toBe(false);
		expect(display.hiddenFromOthers).toEqual({
			reason: false,
			dice: false,
			result: false,
		});
	});

	it("marks what the author set as hidden from others while still seeing it", () => {
		const display = rollDisplay(
			roll({ hide_reason: true, hide_dice: true, hide_result: true }),
		);
		expect(display.hiddenFromOthers).toEqual({
			reason: true,
			dice: true,
			result: true,
		});
		expect(display.reasonWithheld).toBe(false);
		expect(display.resultWithheld).toBe(false);
	});

	it("treats a redacted reason as withheld and not as hidden-from-others", () => {
		const display = rollDisplay(roll({ reason: null, hide_reason: true }));
		expect(display.reasonWithheld).toBe(true);
		expect(display.hiddenFromOthers.reason).toBe(false);
	});

	it("shows only the outcome when the dice are hidden but the result isn't", () => {
		const display = rollDisplay(
			roll({
				input: null,
				options: null,
				result: null,
				summary: { total: 7 },
				hide_dice: true,
			}),
		);
		expect(display.inputWithheld).toBe(true);
		expect(display.summaryOnly).toBe(true);
		expect(display.resultWithheld).toBe(false);
		expect(display.hiddenFromOthers.dice).toBe(false);
	});

	it("withholds the result when neither result nor summary is present", () => {
		const display = rollDisplay(roll({ result: null, hide_result: true }));
		expect(display.resultWithheld).toBe(true);
		expect(display.summaryOnly).toBe(false);
		expect(display.inputWithheld).toBe(false);
	});
});

describe("hiddenTag", () => {
	const flags = (reason: boolean, dice: boolean, result: boolean) => ({
		reason,
		dice,
		result,
	});

	it("is null when nothing is hidden from others", () => {
		expect(hiddenTag(flags(false, false, false))).toBeNull();
	});

	it("names a single hidden part", () => {
		expect(hiddenTag(flags(true, false, false))).toBe("Reason hidden");
		expect(hiddenTag(flags(false, false, true))).toBe("Result hidden");
	});

	it("joins two hidden parts in a fixed order", () => {
		expect(hiddenTag(flags(true, true, false))).toBe("Reason & dice hidden");
		expect(hiddenTag(flags(false, true, true))).toBe("Dice & result hidden");
	});

	it("says all hidden when every part is", () => {
		expect(hiddenTag(flags(true, true, true))).toBe("All hidden");
	});
});

describe("rollParens", () => {
	it("is just the dice for a roll with no options", () => {
		expect(rollParens(roll())).toBe("2d6");
	});

	it("is null when the dice are withheld", () => {
		expect(rollParens(roll({ input: null, options: null }))).toBeNull();
	});

	it("marks rerolled aces on a basic roll", () => {
		expect(rollParens(roll({ options: { reroll_aces: true } }))).toBe("2d6, RA");
		expect(rollParens(roll({ options: { reroll_aces: false } }))).toBe("2d6");
	});

	it("shows a non-zero fate modifier with its sign", () => {
		const fate = { type: "fate" as const, input: "4" };
		expect(rollParens(roll({ ...fate, options: { modifier: 2 } }))).toBe("4, +2");
		expect(rollParens(roll({ ...fate, options: { modifier: -1 } }))).toBe("4, -1");
		expect(rollParens(roll({ ...fate, options: { modifier: 0 } }))).toBe("4");
	});

	it("shows a feng shui roll type other than standard", () => {
		const fengshui = { type: "fengshui" as const, input: "12" };
		expect(rollParens(roll({ ...fengshui, options: { roll_type: "fortune" } }))).toBe(
			"12, Fortune",
		);
		expect(rollParens(roll({ ...fengshui, options: { roll_type: "standard" } }))).toBe(
			"12",
		);
	});

	it("ignores options that belong to another system", () => {
		expect(
			rollParens(roll({ type: "fate", input: "4", options: { reroll_aces: true } })),
		).toBe("4");
	});
});

describe("summaryText", () => {
	it("gives the total for summaries with one", () => {
		expect(summaryText({ total: 12 })).toBe("Total: 12");
	});

	it("gives the net outcome of a Star Wars FFG roll", () => {
		expect(
			summaryText({ net_success: 2, net_advantage: -1, triumph: 1, despair: 0 }),
		).toBe("Total: 2 Success, 1 Threat, 1 Triumph");
		expect(
			summaryText({ net_success: -1, net_advantage: 3, triumph: 0, despair: 1 }),
		).toBe("Total: 1 Failure, 3 Advantage, 1 Despair");
	});

	it("says so when a Star Wars FFG roll nets out to nothing", () => {
		expect(
			summaryText({ net_success: 0, net_advantage: 0, triumph: 0, despair: 0 }),
		).toBe("Total: no net result");
	});
});

describe("changedRollVisibility", () => {
	const rolls = [
		roll({ id: 1 }),
		roll({ id: 2, hide_dice: true }),
		roll({ id: 3, hide_result: true }),
	];

	it("sends nothing when the flags are untouched", () => {
		expect(changedRollVisibility(rolls, initialVisibility(rolls))).toEqual([]);
	});

	it("sends only the rolls whose flags changed, with all three flags", () => {
		const flags = initialVisibility(rolls);
		flags[1] = { ...flags[1], hideReason: true };
		flags[3] = { ...flags[3], hideResult: false };
		expect(changedRollVisibility(rolls, flags)).toEqual([
			{ id: 1, hide_reason: true, hide_dice: false, hide_result: false },
			{ id: 3, hide_reason: false, hide_dice: false, hide_result: false },
		]);
	});

	it("ignores a roll with no edit state", () => {
		expect(changedRollVisibility(rolls, {})).toEqual([]);
	});
});
