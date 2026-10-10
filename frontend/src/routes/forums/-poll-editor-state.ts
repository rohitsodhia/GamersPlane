import type { PollData, PollInput } from "#/queries/threads";

// Limits mirror poll_schemas.py in the API.
export const MAX_POLL_TEXT_LENGTH = 200;
export const MIN_POLL_OPTIONS = 2;
export const MAX_POLL_OPTIONS = 25;

// Form state for a poll. Rows carry a client-only `key` (new rows have no API id);
// `id` and `votes` are set for options loaded from the API.
export type PollOptionRow = {
	key: string;
	id: number | null;
	text: string;
	votes: number;
};

export type PollState = {
	question: string;
	optionsPerUser: number;
	allowRevoting: boolean;
	options: PollOptionRow[];
};

export function newOptionRow(text = ""): PollOptionRow {
	return { key: crypto.randomUUID(), id: null, text, votes: 0 };
}

export function newPollState(): PollState {
	return {
		question: "",
		optionsPerUser: 1,
		allowRevoting: false,
		options: [newOptionRow(), newOptionRow()],
	};
}

export function pollStateFromData(poll: PollData): PollState {
	return {
		question: poll.question,
		optionsPerUser: poll.options_per_user,
		allowRevoting: poll.allow_revoting,
		options: poll.options.map((option) => ({
			key: crypto.randomUUID(),
			id: option.id,
			text: option.text,
			votes: option.votes ?? 0,
		})),
	};
}

// "Options per voter" can't exceed the number of options.
export function clampOptionsPerUser(state: PollState): PollState {
	const max = Math.max(1, state.options.length);
	return state.optionsPerUser > max ? { ...state, optionsPerUser: max } : state;
}

export function removeOption(state: PollState, key: string): PollState {
	return clampOptionsPerUser({
		...state,
		options: state.options.filter((row) => row.key !== key),
	});
}

export function totalVotes(options: PollOptionRow[]): number {
	return options.reduce((sum, row) => sum + row.votes, 0);
}

// Moves the rows with `movedKeys` next to the target row, keeping their own order.
export function moveRows(
	rows: PollOptionRow[],
	movedKeys: Iterable<string | number>,
	targetKey: string | number,
	position: "before" | "after",
): PollOptionRow[] {
	const moving = new Set(movedKeys);
	if (moving.has(targetKey)) return rows;
	const moved = rows.filter((row) => moving.has(row.key));
	const rest = rows.filter((row) => !moving.has(row.key));
	const at = rest.findIndex((row) => row.key === targetKey);
	if (at === -1) return rows;
	rest.splice(position === "before" ? at : at + 1, 0, ...moved);
	return rest;
}

// Pasting text with line breaks into an option fills it and spills the other lines
// into new rows right after it (up to the option limit). The first line replaces
// the row's text if that's blank, otherwise it goes in at the cursor, replacing any
// selection. Returns null when there's nothing to split, so the browser's own
// paste can run.
export function applyPaste(
	rows: PollOptionRow[],
	key: string,
	pasted: string,
	selectionStart: number,
	selectionEnd: number,
): PollOptionRow[] | null {
	if (!/[\r\n]/.test(pasted)) return null;
	const lines = pasted
		.split(/\r?\n|\r/)
		.map((line) => line.trim())
		.filter(Boolean);
	const index = rows.findIndex((row) => row.key === key);
	if (lines.length === 0 || index === -1) return null;

	const [first, ...others] = lines as [string, ...string[]];
	const current = rows[index] as PollOptionRow;
	const text = current.text.trim()
		? current.text.slice(0, selectionStart) + first + current.text.slice(selectionEnd)
		: first;
	const room = Math.max(0, MAX_POLL_OPTIONS - rows.length);
	const added = others
		.slice(0, room)
		.map((line) => newOptionRow(line.slice(0, MAX_POLL_TEXT_LENGTH)));
	return [
		...rows.slice(0, index),
		{ ...current, text: text.slice(0, MAX_POLL_TEXT_LENGTH) },
		...added,
		...rows.slice(index + 1),
	];
}

export type PollErrors = {
	question?: string;
	// About the options as a whole (how many, how many per voter).
	options?: string;
	// By row key.
	rows: Record<string, string>;
};

export function pollErrors(state: PollState): PollErrors {
	const errors: PollErrors = { rows: {} };
	if (!state.question.trim()) errors.question = "Enter a question.";

	const count = state.options.length;
	if (count < MIN_POLL_OPTIONS)
		errors.options = `A poll needs at least ${MIN_POLL_OPTIONS} options.`;
	else if (count > MAX_POLL_OPTIONS)
		errors.options = `A poll can have at most ${MAX_POLL_OPTIONS} options.`;
	else if (state.optionsPerUser < 1 || state.optionsPerUser > count)
		errors.options = `Options per voter must be between 1 and ${count}.`;

	const seen = new Set<string>();
	for (const row of state.options) {
		const text = row.text.trim();
		if (!text) {
			errors.rows[row.key] = "Enter the option's text.";
			continue;
		}
		const folded = text.toLowerCase();
		if (seen.has(folded)) errors.rows[row.key] = "This matches another option.";
		seen.add(folded);
	}
	return errors;
}

export function hasPollErrors(errors: PollErrors): boolean {
	return (
		Boolean(errors.question) ||
		Boolean(errors.options) ||
		Object.keys(errors.rows).length > 0
	);
}

export function buildPollInput(state: PollState): PollInput {
	return {
		question: state.question.trim(),
		options_per_user: state.optionsPerUser,
		allow_revoting: state.allowRevoting,
		options: state.options.map((row) => ({
			...(row.id === null ? {} : { id: row.id }),
			text: row.text.trim(),
		})),
	};
}

// What goes in the request's `poll` key, given the poll as loaded (null for none)
// and as it is now: undefined (omit the key) when unchanged, null to remove the
// poll, otherwise the poll to save.
export function pollPayload(
	initial: PollState | null,
	current: PollState | null,
): PollInput | null | undefined {
	if (current === null) return initial === null ? undefined : null;
	const input = buildPollInput(current);
	if (initial !== null && sameJson(buildPollInput(initial), input)) return undefined;
	return input;
}

function sameJson(a: unknown, b: unknown): boolean {
	return JSON.stringify(a) === JSON.stringify(b);
}
