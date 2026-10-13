import type { DiceSystem, FengShuiRollType } from "#/queries/dice";
import type { DrawableDeck, ForumPermission } from "#/queries/forums";
import {
	MAX_ROLLS_PER_POST,
	type NewDrawInput,
	type NewRollInput,
} from "#/queries/posts";
import type { ThreadOptions } from "#/queries/threads";

// Form state for the rolls and draws a post adds. Numbers stay strings while
// typing; `buildAttachmentPayload` turns them into the API's shape.
export type RollRow = {
	key: string;
	system: DiceSystem;
	roll: string;
	reason: string;
	rerollAces: boolean;
	modifier: string;
	rollType: FengShuiRollType;
	hideReason: boolean;
	hideDice: boolean;
	hideResult: boolean;
};

export type DrawRow = {
	key: string;
	deckId: number | null;
	count: string;
	reason: string;
};

export type Attachments = {
	rolls: RollRow[];
	draws: DrawRow[];
};

export type AttachmentAccess = { rolls: boolean; draws: boolean };

export const emptyAttachments: Attachments = { rolls: [], draws: [] };

export function newRollRow(): RollRow {
	return {
		key: crypto.randomUUID(),
		system: "basic",
		roll: "",
		reason: "",
		rerollAces: false,
		modifier: "0",
		rollType: "standard",
		hideReason: false,
		hideDice: false,
		hideResult: false,
	};
}

// Starts on the first deck no other draw has picked.
export function newDrawRow(decks: DrawableDeck[], draws: DrawRow[]): DrawRow {
	return {
		key: crypto.randomUUID(),
		deckId: availableDecks(decks, draws, null)[0]?.id ?? null,
		count: "1",
		reason: "",
	};
}

// A post can draw from each deck once, so a row's choices are the decks no other
// row has taken (plus its own pick).
export function availableDecks(
	decks: DrawableDeck[],
	draws: DrawRow[],
	rowKey: string | null,
): DrawableDeck[] {
	const taken = new Set(
		draws.filter((row) => row.key !== rowKey).map((row) => row.deckId),
	);
	return decks.filter((deck) => !taken.has(deck.id));
}

// Rolls need the thread to allow them and the permission (moderators have every
// permission); draws likewise.
export function attachmentAccess(
	options: Pick<ThreadOptions, "allow_rolls" | "allow_draws">,
	permissions: ForumPermission[],
): AttachmentAccess {
	const moderator = permissions.includes("forum_moderate");
	return {
		rolls:
			options.allow_rolls && (moderator || permissions.includes("forum_add_rolls")),
		draws:
			options.allow_draws && (moderator || permissions.includes("forum_add_draws")),
	};
}

// Why a sheet roll can't be added to the post, or null when it can. `off` is the
// message for rolls being switched off, which differs between a new thread (the
// checkbox is on the same page) and an existing one.
export function rollsBlockedReason(
	options: Pick<ThreadOptions, "allow_rolls">,
	permissions: ForumPermission[],
	off = "Rolls are turned off in this thread.",
): string | null {
	const allowed =
		permissions.includes("forum_moderate") || permissions.includes("forum_add_rolls");
	if (!allowed) return "You can't add rolls in this forum.";
	return options.allow_rolls ? null : off;
}

export type AddedRoll = { attachments: Attachments; rowKey: string };

// Puts a roll from a character sheet into the post's rolls. `add` mode extends the
// latest basic roll as another comma group (the roller's dice-pool form), keeping
// its reason unless it has none; with no basic roll to extend, or for a `new`
// roll, it starts a row, which a full post refuses. Nothing here rolls: the dice
// are rolled when the post is saved.
export function addSheetRoll(
	attachments: Attachments,
	roll: { dice: string; reason: string; mode: "new" | "add" },
): AddedRoll | { error: string } {
	const target =
		roll.mode === "add"
			? attachments.rolls.filter((row) => row.system === "basic").at(-1)
			: undefined;
	if (target) {
		const current = target.roll.trim();
		const extended: RollRow = {
			...target,
			roll: current ? `${current},${roll.dice}` : roll.dice,
			reason: target.reason.trim() ? target.reason : roll.reason,
		};
		return {
			rowKey: target.key,
			attachments: {
				...attachments,
				rolls: attachments.rolls.map((row) =>
					row.key === target.key ? extended : row,
				),
			},
		};
	}
	if (attachments.rolls.length >= MAX_ROLLS_PER_POST) {
		return { error: `A post can have at most ${MAX_ROLLS_PER_POST} rolls.` };
	}
	const row: RollRow = { ...newRollRow(), roll: roll.dice, reason: roll.reason };
	return {
		rowKey: row.key,
		attachments: { ...attachments, rolls: [...attachments.rolls, row] },
	};
}

export type RowErrors = Record<string, string>;

// Errors by row key, for the rows that would be sent.
export function attachmentErrors(
	attachments: Attachments,
	access: AttachmentAccess,
	decks: DrawableDeck[],
): RowErrors {
	const errors: RowErrors = {};
	if (access.rolls) {
		for (const row of attachments.rolls) {
			if (!row.roll.trim()) errors[row.key] = "Enter what to roll.";
		}
	}
	if (access.draws) {
		for (const row of attachments.draws) {
			const deck = decks.find((candidate) => candidate.id === row.deckId);
			const count = Number(row.count);
			if (!deck) errors[row.key] = "Pick a deck.";
			else if (!Number.isInteger(count) || count < 1 || count > deck.remaining)
				errors[row.key] = `Draw between 1 and ${deck.remaining} cards.`;
			else if (!row.reason.trim()) errors[row.key] = "A draw needs a reason.";
		}
	}
	return errors;
}

// Only what the user may add is sent, and each roll carries just the option its
// system reads.
export function buildAttachmentPayload(
	attachments: Attachments,
	access: AttachmentAccess,
): { rolls: NewRollInput[]; draws: NewDrawInput[] } {
	const rolls = access.rolls
		? attachments.rolls.map((row): NewRollInput => {
				const options: NewRollInput["options"] = {};
				if (row.system === "basic") options.reroll_aces = row.rerollAces;
				if (row.system === "fate")
					options.modifier = Number.parseInt(row.modifier, 10) || 0;
				if (row.system === "fengshui") options.roll_type = row.rollType;
				return {
					type: row.system,
					roll: row.roll.trim(),
					reason: row.reason.trim(),
					options,
					hide_reason: row.hideReason,
					hide_dice: row.hideDice,
					hide_result: row.hideResult,
				};
			})
		: [];
	const draws = access.draws
		? attachments.draws.flatMap((row): NewDrawInput[] =>
				row.deckId === null
					? []
					: [
							{
								deck_id: row.deckId,
								count: Number(row.count),
								reason: row.reason.trim(),
							},
						],
			)
		: [];
	return { rolls, draws };
}
