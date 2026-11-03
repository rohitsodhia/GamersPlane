import type { MeNotificationsResponse } from "#/queries/me";

const plural = (count: number, singular: string) =>
	`${count} ${singular}${count === 1 ? "" : "s"}`;

/**
 * The bell line for a game with things waiting on its GM, e.g.
 * "2 players and 1 character pending in Campaign". A zero count is left out.
 */
export function pendingText(
	players: number,
	characters: number,
	title: string,
): string {
	const parts = [
		players > 0 ? plural(players, "player") : null,
		characters > 0 ? plural(characters, "character") : null,
	].filter((part) => part !== null);
	return `${parts.join(" and ")} pending in ${title}`;
}

export type NotificationItem = { key: string; gameId: number; text: string };

/** The most items the header dropdown shows before linking to the full page. */
export const DROPDOWN_LIMIT = 5;

/** Every current notification, invites first, then pending, each in API order. */
export function buildNotificationItems(
	notifications: MeNotificationsResponse,
): NotificationItem[] {
	return [
		...notifications.invites.map((item) => ({
			key: `invite-${item.gameId}`,
			gameId: item.gameId,
			text: `You've been invited to ${item.title}`,
		})),
		...notifications.pending.map((item) => ({
			key: `pending-${item.gameId}`,
			gameId: item.gameId,
			text: pendingText(item.players, item.characters, item.title),
		})),
	];
}

/** The items the dropdown shows, and whether a "View all" line is needed. */
export function dropdownItems(items: NotificationItem[]): {
	shown: NotificationItem[];
	hasMore: boolean;
} {
	return {
		shown: items.slice(0, DROPDOWN_LIMIT),
		hasMore: items.length > DROPDOWN_LIMIT,
	};
}
