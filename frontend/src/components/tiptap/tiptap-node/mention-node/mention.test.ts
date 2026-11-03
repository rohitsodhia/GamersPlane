import { generateHTML } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import {
	addMentions,
	findMentionNames,
	mentionHref,
	mentionLabel,
	mentionLookup,
	stepIndex,
} from "./mention";
import { Mention } from "./mention-node-extension";

const users = [
	{ id: 1, username: "Alice" },
	{ id: 2, username: "Bob" },
];

describe("mentionLabel", () => {
	it("is @ and the username for a listed user", () => {
		expect(mentionLabel(1, mentionLookup(users))).toBe("@Alice");
	});

	it("is @[deleted] for an unlisted or malformed id", () => {
		const lookup = mentionLookup(users);

		expect(mentionLabel(99, lookup)).toBe("@[deleted]");
		expect(mentionLabel(null, lookup)).toBe("@[deleted]");
		expect(mentionLabel("1", lookup)).toBe("@[deleted]");
	});
});

describe("mentionHref", () => {
	it("links a listed user to their profile", () => {
		expect(mentionHref(2, mentionLookup(users))).toBe("/user/2");
	});

	it("doesn't link an unknown user", () => {
		expect(mentionHref(99, mentionLookup(users))).toBeNull();
	});
});

describe("findMentionNames", () => {
	it("prefers a freshly picked user's name over the post's copy", () => {
		const names = findMentionNames(
			[{ id: 1, username: "Alicia" }],
			[users[0], users[1]],
		);

		expect(names).toEqual({ 1: "Alicia", 2: "Bob" });
	});
});

describe("stepIndex", () => {
	it("moves down and up through the items, wrapping at both ends", () => {
		expect(stepIndex(0, 1, 3)).toBe(1);
		expect(stepIndex(2, 1, 3)).toBe(0);
		expect(stepIndex(0, -1, 3)).toBe(2);
	});

	it("stays at 0 when there are no items", () => {
		expect(stepIndex(0, 1, 0)).toBe(0);
	});
});

describe("addMentions", () => {
	it("adds only the users not already listed, keeping order", () => {
		const added = [
			{ id: 2, username: "Bobby" },
			{ id: 3, username: "Cy" },
		];

		expect(addMentions(users, added)).toEqual([...users, { id: 3, username: "Cy" }]);
	});
});

describe("Mention rendering", () => {
	const body = (userId: unknown) => ({
		type: "doc",
		content: [
			{
				type: "paragraph",
				content: [{ type: "mention", attrs: { userId } }],
			},
		],
	});

	it("renders a listed user as a profile link", () => {
		const html = generateHTML(body(1), [
			StarterKit,
			Mention.configure({ users: mentionLookup(users) }),
		]);

		expect(html).toContain("<a ");
		expect(html).toContain('href="/user/1"');
		expect(html).toContain("@Alice");
	});

	it("renders an unknown user as plain @[deleted] text", () => {
		const html = generateHTML(body(99), [
			StarterKit,
			Mention.configure({ users: mentionLookup(users) }),
		]);

		expect(html).not.toContain("<a ");
		expect(html).toContain("mention-deleted");
		expect(html).toContain("@[deleted]");
	});
});
