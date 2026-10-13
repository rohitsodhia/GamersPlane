// Pure helpers for a `roll` spec (see `RollSpec` in `types.ts`): build the dice
// string + reason from a spec, validate it against the basic roller's grammar,
// and apply advantage. No React, no store — the ref resolver is injected, like
// `resolveClickValue` in `Button.tsx`, so all of it is unit-testable.

import type { RefResolver } from "./formula";
import type { RollSpec } from "./types";

/** What the host receives when a roll is activated. */
export interface RollRequest {
	dice: string;
	reason: string;
	mode: "new" | "add";
}

export interface BuiltRoll extends RollRequest {
	/** The spec asked for advantage: `dice` is the normal form (`applyAdvantage` rewrites it). */
	advantage: boolean;
}

export type BuildRollResult = BuiltRoll | { error: string };

export type AdvantageChoice = "advantage" | "normal" | "disadvantage";

/** Matches the API's `NewRollInput.reason` limit. */
export const MAX_REASON_LENGTH = 100;

// Mirrors `api/src/app/tools/dice/basic.py` (TERM_RE, MAX_DICE, MAX_SIDES).
const MAX_DICE = 100;
const MIN_SIDES = 2;
const MAX_SIDES = 1000;
const TERM_RE = /([+-]?)(?:(\d*)d(\d+)(?:([hl])(\d+))?|(\d+))/iy;

/**
 * Why `dice` isn't a string the roller will accept, or null when it is. Same
 * grammar as the basic roller: comma-separated groups of `NdS` / `dS` terms
 * (optional keep `h`/`l` + count) and integer modifiers, signs between terms,
 * spaces ignored, 1..100 dice of 2..1000 sides.
 */
export function diceError(dice: string): string | null {
	const groups = dice.replaceAll(" ", "").split(",");
	let sawTerm = false;
	for (const group of groups) {
		if (group === "") continue;
		let pos = 0;
		while (pos < group.length) {
			TERM_RE.lastIndex = pos;
			const match = TERM_RE.exec(group);
			if (match == null) return `"${dice}" isn't a valid dice expression`;
			pos = TERM_RE.lastIndex;
			sawTerm = true;
			if (match[3] != null) {
				const count = match[2] ? Number(match[2]) : 1;
				const sides = Number(match[3]);
				if (count < 1 || count > MAX_DICE) {
					return `"${dice}" rolls ${count} dice; use 1 to ${MAX_DICE}`;
				}
				if (sides < MIN_SIDES || sides > MAX_SIDES) {
					return `"${dice}" has a d${sides}; dice need ${MIN_SIDES} to ${MAX_SIDES} sides`;
				}
			}
		}
	}
	return sawTerm ? null : "the roll has no dice";
}

// A single-die d20 term: `d20` or `1d20`, on its own (not 11d20, not d20h1).
const SINGLE_D20_RE = /(?<=^|[+,-])1?d20(?![0-9hl])/i;

/** `dice` with its first single d20 term made `2d20h1` / `2d20l1`; unchanged for normal. */
export function applyAdvantage(dice: string, choice: AdvantageChoice): string {
	if (choice === "normal") return dice;
	const keep = choice === "advantage" ? "h" : "l";
	return dice.replace(SINGLE_D20_RE, `2d20${keep}1`);
}

// --- templates ---------------------------------------------------------------

export type TemplatePart = { text: string } | { ref: string };

/**
 * Splits a `${ref}` template into literal text and ref paths. A ref runs to the
 * `}` that closes its `${`, skipping any `(…)` / `{…}` nested inside it (a
 * dynamic `$(…)` segment). Only a ref path goes inside: no formulas. Throws
 * `TemplateError` for an unterminated or empty `${}`. (The API mirrors this in
 * `roll_template.py`.)
 */
export function parseTemplate(template: string): TemplatePart[] {
	const parts: TemplatePart[] = [];
	let pos = 0;
	while (pos < template.length) {
		const open = template.indexOf("${", pos);
		if (open === -1) break;
		if (open > pos) parts.push({ text: template.slice(pos, open) });
		let depth = 0;
		let end = -1;
		for (let i = open + 2; i < template.length; i++) {
			const ch = template[i];
			if (ch === "(" || ch === "{") depth++;
			else if (ch === ")") depth--;
			else if (ch === "}") {
				if (depth === 0) {
					end = i;
					break;
				}
				depth--;
			}
		}
		if (end === -1) throw new TemplateError(`unterminated "\${" in "${template}"`);
		const ref = template.slice(open + 2, end).trim();
		if (ref === "") throw new TemplateError(`empty "\${}" in "${template}"`);
		parts.push({ ref });
		pos = end + 1;
	}
	if (pos < template.length) parts.push({ text: template.slice(pos) });
	return parts;
}

export class TemplateError extends Error {
	override name = "TemplateError";
}

/**
 * The integer a `${ref}` in `dice` stands for: numbers truncate, booleans are
 * 0 / 1, a missing or empty value is 0, numeric text (inputs store strings)
 * parses. Anything else is a `TemplateError`.
 */
function diceNumber(ref: string, value: unknown): number {
	if (value == null || value === "") return 0;
	if (typeof value === "boolean") return Number(value);
	const n =
		typeof value === "number"
			? value
			: typeof value === "string" && value.trim() !== ""
				? Number(value)
				: Number.NaN;
	if (!Number.isFinite(n)) {
		const shown = typeof value === "string" ? `'${value}'` : "not a value";
		throw new TemplateError(`\${${ref}} is ${shown}, not a number`);
	}
	return Math.trunc(n);
}

/**
 * Tidies a substituted dice string: strips spaces, collapses runs of signs
 * (`+-` / `-+` to `-`, `--` / `++` to `+`), drops a bare `+0` / `-0` modifier
 * term (never `+0d6`, or the 0 in `10`), and drops a `+` leading a group.
 * Mirrored by the API's static shape check.
 */
export function normalizeDice(dice: string): string {
	return dice
		.replaceAll(" ", "")
		.replace(/[+-]{2,}/g, (run) => ((run.match(/-/g) ?? []).length % 2 ? "-" : "+"))
		.replace(/[+-]0(?![0-9d])/gi, "")
		.replace(/(^|,)\+/g, "$1");
}

function refText(value: unknown): string {
	return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function capReason(reason: string): string {
	return reason.trim().slice(0, MAX_REASON_LENGTH);
}

/**
 * Builds the roll a spec describes in the current scope. Never throws for bad
 * input: a malformed template, a non-numeric `${ref}`, a dice string the roller
 * would reject, or `advantage` without a single d20 comes back as `{ error }` so
 * the caller can show it instead of silently doing nothing. `fallbackReason` is
 * the element's own text, used when the spec has no `reason`.
 */
export function buildRoll(
	spec: RollSpec,
	resolve: RefResolver,
	fallbackReason: string,
): BuildRollResult {
	let dice: string;
	let reason: string;
	try {
		dice = normalizeDice(
			parseTemplate(spec.dice)
				.map((part) =>
					"text" in part ? part.text : String(diceNumber(part.ref, resolve(part.ref))),
				)
				.join(""),
		);
		reason = capReason(
			spec.reason == null
				? fallbackReason
				: parseTemplate(spec.reason)
						.map((part) => ("text" in part ? part.text : refText(resolve(part.ref))))
						.join(""),
		);
	} catch (err) {
		if (err instanceof TemplateError) return { error: err.message };
		throw err;
	}

	const invalid = diceError(dice);
	if (invalid != null) return { error: invalid };

	const advantage = spec.advantage === true;
	if (advantage && !SINGLE_D20_RE.test(dice)) {
		return { error: `"${dice}" has no single d20 for advantage` };
	}

	return { dice, reason, mode: spec.mode ?? "new", advantage };
}

// Elements a click should be left to: forwarding it to the roll would fight
// whatever the user meant to press. `label` is deliberately absent: rolls only
// exist in display mode, where no control is there for a label to activate, and
// a label is usually the title of the row being rolled.
const INTERACTIVE =
	'button, a[href], input, select, textarea, summary, [role="button"], [role="switch"], [role="checkbox"], [role="combobox"], [role="listbox"], [role="menuitem"], [contenteditable]:not([contenteditable="false"])';

/**
 * True when a click on `target` landed on an interactive descendant of
 * `boundary` (so the element-wide roll click must not also fire). The boundary
 * itself and anything outside it never count.
 */
export function isInteractiveTarget(
	target: EventTarget | null,
	boundary: Element,
): boolean {
	if (!(target instanceof Element)) return false;
	const hit = target.closest(INTERACTIVE);
	return hit != null && hit !== boundary && boundary.contains(hit);
}
