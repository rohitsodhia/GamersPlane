import type { DiceSystem } from "#/queries/dice";
import type { PostRoll, PostRollSummary, RollVisibilityInput } from "#/queries/posts";

export const SYSTEM_LABELS: Record<DiceSystem, string> = {
	basic: "Basic",
	starwarsffg: "Star Wars FFG",
	fate: "Fate",
	fengshui: "Feng Shui",
};

export type RollDisplay = {
	// Withheld from this viewer (null, as opposed to a roll with no reason).
	reasonWithheld: boolean;
	inputWithheld: boolean;
	resultWithheld: boolean;
	// Only the outcome is visible: dice hidden, result not.
	summaryOnly: boolean;
	// For viewers who see everything, the parts other people can't see.
	hiddenFromOthers: { reason: boolean; dice: boolean; result: boolean };
};

// A viewer who sees everything is recognised by a flag being set while the field
// it hides is still present.
export function rollDisplay(roll: PostRoll): RollDisplay {
	return {
		reasonWithheld: roll.reason === null,
		inputWithheld: roll.input === null,
		resultWithheld: roll.result === null && roll.summary === null,
		summaryOnly: roll.result === null && roll.summary !== null,
		hiddenFromOthers: {
			reason: roll.hide_reason && roll.reason !== null,
			dice: roll.hide_dice && roll.input !== null,
			result: roll.hide_result && roll.result !== null,
		},
	};
}

// The muted tag a viewer who sees everything gets, naming what others can't see.
export function hiddenTag(
	hiddenFromOthers: RollDisplay["hiddenFromOthers"],
): string | null {
	const parts: string[] = [];
	if (hiddenFromOthers.reason) parts.push("reason");
	if (hiddenFromOthers.dice) parts.push("dice");
	if (hiddenFromOthers.result) parts.push("result");
	if (parts.length === 0) return null;
	if (parts.length === 3) return "All hidden";
	const [first, ...rest] = parts;
	return `${first[0].toUpperCase()}${first.slice(1)}${rest.map((part) => ` & ${part}`).join("")} hidden`;
}

// The parenthesised part of a roll's first line: the dice plus any option that
// changed the roll. Null when the viewer can't see the dice.
export function rollParens(roll: PostRoll): string | null {
	if (roll.input === null) return null;
	const parts = [roll.input];
	const options = roll.options ?? {};
	if (roll.type === "basic" && options["reroll_aces"] === true) parts.push("RA");
	if (roll.type === "fate" && typeof options["modifier"] === "number") {
		if (options["modifier"] !== 0) {
			parts.push(`${options["modifier"] > 0 ? "+" : ""}${options["modifier"]}`);
		}
	}
	if (
		roll.type === "fengshui" &&
		typeof options["roll_type"] === "string" &&
		options["roll_type"] !== "standard"
	) {
		const rollType = options["roll_type"];
		parts.push(`${rollType[0].toUpperCase()}${rollType.slice(1)}`);
	}
	return parts.join(", ");
}

export function summaryText(summary: PostRollSummary): string {
	if ("total" in summary) return `Total: ${summary.total}`;
	const parts: string[] = [];
	if (summary.net_success !== 0) {
		parts.push(
			`${Math.abs(summary.net_success)} ${summary.net_success > 0 ? "Success" : "Failure"}`,
		);
	}
	if (summary.net_advantage !== 0) {
		parts.push(
			`${Math.abs(summary.net_advantage)} ${summary.net_advantage > 0 ? "Advantage" : "Threat"}`,
		);
	}
	if (summary.triumph) parts.push(`${summary.triumph} Triumph`);
	if (summary.despair) parts.push(`${summary.despair} Despair`);
	return `Total: ${parts.length > 0 ? parts.join(", ") : "no net result"}`;
}

// The edit form's state for one roll's visibility flags.
export type VisibilityFlags = {
	hideReason: boolean;
	hideDice: boolean;
	hideResult: boolean;
};

export function initialVisibility(rolls: PostRoll[]): Record<number, VisibilityFlags> {
	return Object.fromEntries(
		rolls.map((roll) => [
			roll.id,
			{
				hideReason: roll.hide_reason,
				hideDice: roll.hide_dice,
				hideResult: roll.hide_result,
			},
		]),
	);
}

// Only the rolls whose flags differ from what the post has are sent.
export function changedRollVisibility(
	rolls: PostRoll[],
	flags: Record<number, VisibilityFlags>,
): RollVisibilityInput[] {
	return rolls.flatMap((roll): RollVisibilityInput[] => {
		const edited = flags[roll.id];
		if (
			!edited ||
			(edited.hideReason === roll.hide_reason &&
				edited.hideDice === roll.hide_dice &&
				edited.hideResult === roll.hide_result)
		)
			return [];
		return [
			{
				id: roll.id,
				hide_reason: edited.hideReason,
				hide_dice: edited.hideDice,
				hide_result: edited.hideResult,
			},
		];
	});
}
