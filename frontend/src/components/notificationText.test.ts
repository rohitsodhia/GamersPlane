import { describe, expect, it } from "vitest";
import type { MeNotificationsResponse } from "#/queries/me";
import {
	buildNotificationItems,
	dropdownItems,
	type NotificationItem,
	pendingText,
} from "./notificationText";

describe("buildNotificationItems", () => {
	it("puts invites before pending and keeps API order within each group", () => {
		const response: MeNotificationsResponse = {
			pending: [
				{ gameId: 1, title: "Alpha", players: 2, characters: 0 },
				{ gameId: 2, title: "Beta", players: 0, characters: 1 },
			],
			invites: [
				{ gameId: 3, title: "Gamma" },
				{ gameId: 4, title: "Delta" },
			],
			mentions: [],
			hasMoreMentions: false,
			count: 4,
		};
		expect(buildNotificationItems(response)).toEqual([
			{
				kind: "game",
				key: "invite-3",
				gameId: 3,
				text: "You've been invited to Gamma",
			},
			{
				kind: "game",
				key: "invite-4",
				gameId: 4,
				text: "You've been invited to Delta",
			},
			{ kind: "game", key: "pending-1", gameId: 1, text: "2 players pending in Alpha" },
			{
				kind: "game",
				key: "pending-2",
				gameId: 2,
				text: "1 character pending in Beta",
			},
		]);
	});

	it("puts mentions after game items, keeping read ones and API order", () => {
		const mention = (eventId: number, read: boolean) => ({
			eventId,
			actor: { id: 9, username: "Ann" },
			threadId: 10,
			threadTitle: "Thread",
			postId: 100 + eventId,
			forumId: 1,
			createdAt: "2026-11-01T00:00:00Z",
			read,
		});
		const items = buildNotificationItems({
			pending: [{ gameId: 1, title: "Alpha", players: 1, characters: 0 }],
			invites: [],
			mentions: [mention(7, false), mention(5, true)],
		});
		expect(items.map((item) => item.key)).toEqual([
			"pending-1",
			"mention-7",
			"mention-5",
		]);
		expect(items[1]).toEqual({
			kind: "mention",
			key: "mention-7",
			eventId: 7,
			threadId: 10,
			postId: 107,
			actorName: "Ann",
			threadTitle: "Thread",
			read: false,
		});
		expect(items[2]).toMatchObject({ read: true });
	});
});

describe("dropdownItems", () => {
	const make = (n: number): NotificationItem[] =>
		Array.from({ length: n }, (_, i) => ({
			kind: "game",
			key: `invite-${i}`,
			gameId: i,
			text: `Item ${i}`,
		}));

	it("shows exactly five items without a View all line", () => {
		const { shown, hasMore } = dropdownItems(make(5));
		expect(shown).toHaveLength(5);
		expect(hasMore).toBe(false);
	});

	it("cuts six items to the first five and asks for a View all line", () => {
		const { shown, hasMore } = dropdownItems(make(6));
		expect(shown.map((item) => item.key)).toEqual([
			"invite-0",
			"invite-1",
			"invite-2",
			"invite-3",
			"invite-4",
		]);
		expect(hasMore).toBe(true);
	});

	it("asks for a View all line when the server holds more mentions", () => {
		expect(dropdownItems(make(2), true).hasMore).toBe(true);
	});
});

describe("pendingText", () => {
	it("joins players and characters with 'and'", () => {
		expect(pendingText(2, 3, "Dungeon")).toBe(
			"2 players and 3 characters pending in Dungeon",
		);
	});

	it("uses singular forms for a count of one", () => {
		expect(pendingText(1, 1, "Dungeon")).toBe(
			"1 player and 1 character pending in Dungeon",
		);
	});

	it("omits a zero count and the 'and'", () => {
		expect(pendingText(0, 2, "Dungeon")).toBe("2 characters pending in Dungeon");
		expect(pendingText(1, 0, "Dungeon")).toBe("1 player pending in Dungeon");
	});
});
