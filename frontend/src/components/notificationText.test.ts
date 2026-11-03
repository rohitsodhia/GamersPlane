import { describe, expect, it } from "vitest";
import type { Notification } from "#/queries/me";
import {
	dropdownItems,
	flattenPages,
	notificationPlainText,
	notificationSegments,
} from "./notificationText";

const base = (eventId: number) => ({
	eventId,
	actor: { id: 9, username: "Ann" },
	createdAt: "2026-11-01T00:00:00Z",
	read: false,
});

const invite = (eventId: number): Notification => ({
	...base(eventId),
	type: "game_invite",
	gameId: eventId,
	gameTitle: "Gamma",
});

describe("notificationSegments", () => {
	it("styles the actor bold and the thread italic for a mention", () => {
		const item: Notification = {
			...base(1),
			type: "mention",
			threadId: 10,
			threadTitle: "Thread",
			postId: 100,
			forumId: 1,
		};
		expect(notificationSegments(item)).toEqual([
			{ text: "Ann", style: "strong" },
			{ text: " mentioned you in ", style: "plain" },
			{ text: "Thread", style: "em" },
		]);
	});

	it("words each game type", () => {
		expect(notificationPlainText(invite(1))).toBe("Ann invited you to Gamma");
		expect(
			notificationPlainText({
				...base(2),
				type: "game_application",
				gameId: 2,
				gameTitle: "Gamma",
			}),
		).toBe("Ann applied to Gamma");
	});

	it("names both the character and the game when one is submitted", () => {
		const item: Notification = {
			...base(3),
			type: "character_submitted",
			gameId: 3,
			gameTitle: "Gamma",
			characterId: 4,
			characterName: "Bork",
		};
		expect(notificationSegments(item)).toEqual([
			{ text: "Ann", style: "strong" },
			{ text: " submitted ", style: "plain" },
			{ text: "Bork", style: "em" },
			{ text: " to ", style: "plain" },
			{ text: "Gamma", style: "em" },
		]);
	});
});

describe("dropdownItems", () => {
	const make = (n: number) => Array.from({ length: n }, (_, i) => invite(i));

	it("shows exactly five items without a View all line", () => {
		const { shown, hasMore } = dropdownItems(make(5));
		expect(shown).toHaveLength(5);
		expect(hasMore).toBe(false);
	});

	it("cuts six items to the first five and asks for a View all line", () => {
		const { shown, hasMore } = dropdownItems(make(6));
		expect(shown.map((item) => item.eventId)).toEqual([0, 1, 2, 3, 4]);
		expect(hasMore).toBe(true);
	});

	it("asks for a View all line when the server holds more", () => {
		expect(dropdownItems(make(2), true).hasMore).toBe(true);
	});
});

describe("flattenPages", () => {
	it("keeps order across pages and drops a repeated event", () => {
		const result = flattenPages([
			{ items: [invite(5), invite(4)] },
			{ items: [invite(4), invite(3)] },
		]);
		expect(result.map((item) => item.eventId)).toEqual([5, 4, 3]);
	});
});
