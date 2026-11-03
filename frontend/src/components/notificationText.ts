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

export type GameNotificationItem = {
	kind: "game";
	key: string;
	gameId: number;
	text: string;
};

export type MentionNotificationItem = {
	kind: "mention";
	key: string;
	eventId: number;
	threadId: number;
	postId: number;
	actorName: string;
	threadTitle: string;
	read: boolean;
};

export type NotificationItem = GameNotificationItem | MentionNotificationItem;

/** The most items the header dropdown shows before linking to the full page. */
export const DROPDOWN_LIMIT = 5;

/**
 * Every current notification: invites, then pending games, then mentions
 * (newest first), each in API order.
 */
export function buildNotificationItems(
	notifications: Pick<MeNotificationsResponse, "pending" | "invites" | "mentions">,
): NotificationItem[] {
	return [
		...notifications.invites.map(
			(item): NotificationItem => ({
				kind: "game",
				key: `invite-${item.gameId}`,
				gameId: item.gameId,
				text: `You've been invited to ${item.title}`,
			}),
		),
		...notifications.pending.map(
			(item): NotificationItem => ({
				kind: "game",
				key: `pending-${item.gameId}`,
				gameId: item.gameId,
				text: pendingText(item.players, item.characters, item.title),
			}),
		),
		...notifications.mentions.map(
			(mention): NotificationItem => ({
				kind: "mention",
				key: `mention-${mention.eventId}`,
				eventId: mention.eventId,
				threadId: mention.threadId,
				postId: mention.postId,
				actorName: mention.actor.username,
				threadTitle: mention.threadTitle,
				read: mention.read,
			}),
		),
	];
}

/**
 * The items the dropdown shows, and whether a "View all" line is needed: more
 * items than the cap, or more mentions on the server than were fetched.
 */
export function dropdownItems(
	items: NotificationItem[],
	hasMoreMentions = false,
): {
	shown: NotificationItem[];
	hasMore: boolean;
} {
	return {
		shown: items.slice(0, DROPDOWN_LIMIT),
		hasMore: items.length > DROPDOWN_LIMIT || hasMoreMentions,
	};
}
