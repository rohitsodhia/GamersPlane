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
			count: 4,
		};
		expect(buildNotificationItems(response)).toEqual([
			{ key: "invite-3", gameId: 3, text: "You've been invited to Gamma" },
			{ key: "invite-4", gameId: 4, text: "You've been invited to Delta" },
			{ key: "pending-1", gameId: 1, text: "2 players pending in Alpha" },
			{ key: "pending-2", gameId: 2, text: "1 character pending in Beta" },
		]);
	});

	it("returns an empty list when nothing is waiting", () => {
		expect(buildNotificationItems({ pending: [], invites: [], count: 0 })).toEqual([]);
	});
});

describe("dropdownItems", () => {
	const make = (n: number): NotificationItem[] =>
		Array.from({ length: n }, (_, i) => ({
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
		expect(shown.map((item) => item.gameId)).toEqual([0, 1, 2, 3, 4]);
		expect(hasMore).toBe(true);
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
