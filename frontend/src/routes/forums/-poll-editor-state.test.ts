import { describe, expect, it } from "vitest";
import type { PollData } from "#/queries/threads";
import {
	applyPaste,
	clampOptionsPerUser,
	MAX_POLL_OPTIONS,
	MAX_POLL_TEXT_LENGTH,
	moveRows,
	newOptionRow,
	newPollState,
	type PollOptionRow,
	type PollState,
	pollErrors,
	pollPayload,
	pollStateFromData,
	removeOption,
} from "./-poll-editor-state";

function row(text: string, id: number | null = null, votes = 0): PollOptionRow {
	return { ...newOptionRow(text), id, votes };
}

function poll(overrides: Partial<PollState> = {}): PollState {
	return {
		question: "Which day?",
		optionsPerUser: 1,
		allowRevoting: false,
		options: [row("Friday"), row("Saturday")],
		...overrides,
	};
}

const loaded: PollData = {
	question: "Which day?",
	options_per_user: 2,
	allow_revoting: true,
	options: [
		{ id: 7, text: "Friday", votes: 3 },
		{ id: 9, text: "Saturday", votes: null },
	],
	my_votes: [],
	voted: false,
	can_vote: true,
	show_results: true,
	total_voters: 3,
};

describe("pollStateFromData", () => {
	it("keeps ids and order, and treats hidden counts as zero", () => {
		const state = pollStateFromData(loaded);
		expect(state.options.map((o) => [o.id, o.text, o.votes])).toEqual([
			[7, "Friday", 3],
			[9, "Saturday", 0],
		]);
		expect(state.optionsPerUser).toBe(2);
		expect(state.allowRevoting).toBe(true);
	});
});

describe("newPollState", () => {
	it("starts with two empty options", () => {
		const state = newPollState();
		expect(state.options).toHaveLength(2);
		expect(state.options.every((o) => o.text === "" && o.id === null)).toBe(true);
	});
});

describe("pollErrors", () => {
	it("passes a valid poll", () => {
		expect(pollErrors(poll())).toEqual({ rows: {} });
	});

	it("requires a question", () => {
		expect(pollErrors(poll({ question: "  " })).question).toBeDefined();
	});

	it("requires at least two options", () => {
		expect(pollErrors(poll({ options: [row("Only")] })).options).toMatch(/at least 2/);
	});

	it("allows at most 25 options", () => {
		const options = Array.from({ length: MAX_POLL_OPTIONS + 1 }, (_, i) =>
			row(`o${i}`),
		);
		expect(pollErrors(poll({ options })).options).toMatch(/at most 25/);
	});

	it("flags blank options by row", () => {
		const options = [row("Friday"), row("   ")];
		expect(pollErrors(poll({ options })).rows).toEqual({
			[options[1]?.key as string]: expect.any(String),
		});
	});

	it("flags the later of two duplicates, ignoring case and padding", () => {
		const options = [row("Friday"), row("Saturday"), row("  friday ")];
		expect(pollErrors(poll({ options })).rows).toEqual({
			[options[2]?.key as string]: expect.any(String),
		});
	});

	it("keeps options per voter within 1..options", () => {
		expect(pollErrors(poll({ optionsPerUser: 3 })).options).toMatch(/between 1 and 2/);
		expect(pollErrors(poll({ optionsPerUser: 0 })).options).toMatch(/between 1 and 2/);
	});
});

describe("clampOptionsPerUser and removeOption", () => {
	it("leaves a valid value alone", () => {
		const state = poll({ optionsPerUser: 2 });
		expect(clampOptionsPerUser(state)).toBe(state);
	});

	it("lowers options per voter when options are removed below it", () => {
		const state = poll({
			optionsPerUser: 3,
			options: [row("a"), row("b"), row("c")],
		});
		const after = removeOption(state, state.options[0]?.key as string);
		expect(after.options).toHaveLength(2);
		expect(after.optionsPerUser).toBe(2);
	});
});

describe("moveRows", () => {
	const rows = [row("a"), row("b"), row("c"), row("d")];
	const keys = rows.map((r) => r.key);
	const texts = (list: PollOptionRow[]) => list.map((r) => r.text).join("");

	it("moves a row before a target", () => {
		expect(
			texts(moveRows(rows, [keys[3] as string], keys[0] as string, "before")),
		).toBe("dabc");
	});

	it("moves a row after a target", () => {
		expect(texts(moveRows(rows, [keys[0] as string], keys[2] as string, "after"))).toBe(
			"bcad",
		);
	});

	it("moves several rows together in their own order", () => {
		expect(
			texts(
				moveRows(
					rows,
					[keys[2] as string, keys[0] as string],
					keys[3] as string,
					"after",
				),
			),
		).toBe("bdac");
	});

	it("ignores dropping a row on itself", () => {
		expect(moveRows(rows, [keys[1] as string], keys[1] as string, "after")).toBe(rows);
	});
});

describe("applyPaste", () => {
	const texts = (list: PollOptionRow[] | null) => list?.map((r) => r.text);

	it("returns null for text without line breaks", () => {
		const rows = [row("")];
		expect(applyPaste(rows, rows[0]?.key as string, "single", 0, 0)).toBeNull();
	});

	it("fills an empty row and inserts the rest right after it", () => {
		const rows = [row(""), row("last")];
		expect(
			texts(applyPaste(rows, rows[0]?.key as string, "one\n two \r\n\n three", 0, 0)),
		).toEqual(["one", "two", "three", "last"]);
	});

	it("puts the first line at the cursor of a non-empty row", () => {
		const rows = [row("Hello world")];
		expect(texts(applyPaste(rows, rows[0]?.key as string, "big\nnext", 6, 6))).toEqual([
			"Hello bigworld",
			"next",
		]);
	});

	it("replaces the selection with the first line", () => {
		const rows = [row("Hello world")];
		expect(
			texts(applyPaste(rows, rows[0]?.key as string, "there\nnext", 6, 11)),
		).toEqual(["Hello there", "next"]);
	});

	it("stops at the option limit", () => {
		const rows = Array.from({ length: MAX_POLL_OPTIONS - 1 }, () => row("x"));
		rows[0] = row("");
		const result = applyPaste(rows, rows[0].key, "a\nb\nc\nd", 0, 0);
		expect(result).toHaveLength(MAX_POLL_OPTIONS);
		expect(result?.slice(0, 2).map((r) => r.text)).toEqual(["a", "b"]);
	});

	it("cuts pasted lines to the text limit", () => {
		const rows = [row("")];
		const long = "x".repeat(MAX_POLL_TEXT_LENGTH + 20);
		const result = applyPaste(rows, rows[0]?.key as string, `${long}\n${long}`, 0, 0);
		expect(result?.map((r) => r.text.length)).toEqual([
			MAX_POLL_TEXT_LENGTH,
			MAX_POLL_TEXT_LENGTH,
		]);
	});

	it("returns null when every line is blank", () => {
		const rows = [row("keep")];
		expect(applyPaste(rows, rows[0]?.key as string, "\n  \n", 0, 0)).toBeNull();
	});
});

describe("pollPayload", () => {
	const initial = pollStateFromData(loaded);

	it("omits the key when there was no poll and none was added", () => {
		expect(pollPayload(null, null)).toBeUndefined();
	});

	it("sends a new poll without option ids, trimmed", () => {
		const payload = pollPayload(
			null,
			poll({ question: " Which day? ", options: [row(" Fri "), row("Sat")] }),
		);
		expect(payload).toEqual({
			question: "Which day?",
			options_per_user: 1,
			allow_revoting: false,
			options: [{ text: "Fri" }, { text: "Sat" }],
		});
	});

	it("omits the key when an existing poll is unchanged, even with padded text", () => {
		const padded: PollState = {
			...initial,
			question: ` ${initial.question} `,
			options: initial.options.map((o) => ({ ...o, text: ` ${o.text}` })),
		};
		expect(pollPayload(initial, padded)).toBeUndefined();
	});

	it("sends null when an existing poll is removed", () => {
		expect(pollPayload(initial, null)).toBeNull();
	});

	it("keeps ids for existing options and leaves them off new ones", () => {
		const current: PollState = {
			...initial,
			options: [...initial.options, row("Sunday")],
		};
		expect(pollPayload(initial, current)?.options).toEqual([
			{ id: 7, text: "Friday" },
			{ id: 9, text: "Saturday" },
			{ text: "Sunday" },
		]);
	});

	it("counts a reorder as a change", () => {
		const current: PollState = { ...initial, options: [...initial.options].reverse() };
		expect(pollPayload(initial, current)?.options.map((o) => o.id)).toEqual([9, 7]);
	});

	it("counts a changed setting as a change", () => {
		expect(pollPayload(initial, { ...initial, allowRevoting: false })).toMatchObject({
			allow_revoting: false,
		});
	});
});
