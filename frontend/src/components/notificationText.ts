import type { Notification } from "#/queries/me";

/** One run of a notification's text: plain, the actor (bold), or a name (italic). */
export type TextSegment = {
	text: string;
	style: "plain" | "strong" | "em";
};

/** The most items the header dropdown shows before linking to the full page. */
export const DROPDOWN_LIMIT = 5;

/** The notification's sentence as styled runs, so it renders without HTML injection. */
export function notificationSegments(item: Notification): TextSegment[] {
	const actor: TextSegment = { text: item.actor.username, style: "strong" };
	const name = (text: string): TextSegment => ({ text, style: "em" });
	const plain = (text: string): TextSegment => ({ text, style: "plain" });
	switch (item.type) {
		case "mention":
			return [actor, plain(" mentioned you in "), name(item.threadTitle)];
		case "game_invite":
			return [actor, plain(" invited you to "), name(item.gameTitle)];
		case "game_application":
			return [actor, plain(" applied to "), name(item.gameTitle)];
		case "character_submitted":
			return [
				actor,
				plain(" submitted "),
				name(item.characterName),
				plain(" to "),
				name(item.gameTitle),
			];
	}
}

/** The notification's sentence without styling, e.g. for an aria-label. */
export function notificationPlainText(item: Notification): string {
	return notificationSegments(item)
		.map((segment) => segment.text)
		.join("");
}

/**
 * The items the dropdown shows, and whether a "View all" line is needed: more
 * items than the cap, or more on the server than were fetched.
 */
export function dropdownItems(
	items: Notification[],
	hasMore = false,
): {
	shown: Notification[];
	hasMore: boolean;
} {
	return {
		shown: items.slice(0, DROPDOWN_LIMIT),
		hasMore: items.length > DROPDOWN_LIMIT || hasMore,
	};
}

/**
 * Concatenates pages of notifications, keeping the first occurrence of each
 * event. Reuse can move an event between pages, so a later page may repeat one.
 */
export function flattenPages(pages: { items: Notification[] }[]): Notification[] {
	const seen = new Set<number>();
	const result: Notification[] = [];
	for (const page of pages) {
		for (const item of page.items) {
			if (seen.has(item.eventId)) continue;
			seen.add(item.eventId);
			result.push(item);
		}
	}
	return result;
}
