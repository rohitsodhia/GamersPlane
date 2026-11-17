import type { JSONContent } from "@tiptap/core";
import { describe, expect, it } from "vitest";
import {
	dropUnreadableNotes,
	noteLabel,
	noteMode,
	noteStubText,
	noteUserIds,
} from "./note";

const paragraph = (text: string): JSONContent => ({
	type: "paragraph",
	content: [{ type: "text", text }],
});

const note = (userIds: number[], text = "secret", mode = "note"): JSONContent => ({
	type: "note",
	attrs: { userIds, mode },
	content: [paragraph(text)],
});

const stub = (userIds: number[]): JSONContent => ({
	type: "note",
	attrs: { userIds, mode: "note", hidden: true },
	content: [{ type: "paragraph" }],
});

describe("dropUnreadableNotes", () => {
	it("keeps a note its quoter is a recipient of", () => {
		const nodes = [paragraph("hi"), note([5, 7])];

		expect(dropUnreadableNotes(nodes, { userId: 7, seesAllNotes: false })).toEqual(
			nodes,
		);
	});

	it("drops a note its quoter is not a recipient of", () => {
		const result = dropUnreadableNotes([paragraph("hi"), note([5])], {
			userId: 7,
			seesAllNotes: false,
		});

		expect(result).toEqual([paragraph("hi")]);
	});

	it("keeps every note for a viewer who sees all of them", () => {
		const nodes = [note([5]), note([], "private words", "private")];

		expect(dropUnreadableNotes(nodes, { userId: 7, seesAllNotes: true })).toEqual(
			nodes,
		);
	});

	it("drops every note for a guest", () => {
		const result = dropUnreadableNotes([note([5])], {
			userId: null,
			seesAllNotes: false,
		});

		expect(result).toEqual([]);
	});

	it("never keeps a hidden stub, even for a viewer who sees all notes", () => {
		const result = dropUnreadableNotes([paragraph("hi"), stub([7])], {
			userId: 7,
			seesAllNotes: true,
		});

		expect(result).toEqual([paragraph("hi")]);
	});

	it("reaches notes inside lists and nested quotes", () => {
		const nodes: JSONContent[] = [
			{
				type: "bulletList",
				content: [{ type: "listItem", content: [paragraph("a"), note([5])] }],
			},
			{ type: "quote", content: [paragraph("b"), note([7], "mine")] },
		];

		const result = dropUnreadableNotes(nodes, { userId: 7, seesAllNotes: false });

		expect(JSON.stringify(result)).toContain("mine");
		expect(JSON.stringify(result)).not.toContain("secret");
	});

	it("leaves a container that held only dropped notes with an empty paragraph", () => {
		const nodes: JSONContent[] = [{ type: "quote", content: [note([5])] }];

		const result = dropUnreadableNotes(nodes, { userId: 7, seesAllNotes: false });

		expect(result).toEqual([{ type: "quote", content: [{ type: "paragraph" }] }]);
	});

	it("leaves empty paragraphs alone", () => {
		const nodes: JSONContent[] = [{ type: "paragraph", content: [] }];

		expect(dropUnreadableNotes(nodes, { userId: 7, seesAllNotes: false })).toEqual(
			nodes,
		);
	});

	it("treats a note saved with the old or missing attrs as unreadable", () => {
		const old: JSONContent = { type: "note", attrs: { users: ["bob"] }, content: [] };
		const bare: JSONContent = { type: "note", content: [paragraph("x")] };

		const result = dropUnreadableNotes([old, bare], {
			userId: 7,
			seesAllNotes: false,
		});

		expect(result).toEqual([]);
	});
});

describe("noteUserIds", () => {
	it("keeps the valid ids once each and ignores anything else", () => {
		expect(noteUserIds([3, 3, "4", 0, -1, 1.5, null, 9])).toEqual([3, 9]);
	});

	it("reads a missing or non-list attr as no recipients", () => {
		expect(noteUserIds(undefined)).toEqual([]);
		expect(noteUserIds("3")).toEqual([]);
	});
});

describe("noteMode", () => {
	it("is private only for exactly private", () => {
		expect(noteMode("private")).toBe("private");
		expect(noteMode("note")).toBe("note");
		expect(noteMode(undefined)).toBe("note");
		expect(noteMode("PRIVATE")).toBe("note");
	});
});

describe("noteLabel", () => {
	it("ends in a colon only when names follow", () => {
		expect(noteLabel("note", true)).toBe("Note for:");
		expect(noteLabel("private", true)).toBe("Private note for:");
		expect(noteLabel("note", false)).toBe("Note");
		expect(noteLabel("private", false)).toBe("Private note");
	});
});

describe("noteStubText", () => {
	it("names the author and the recipients", () => {
		expect(noteStubText("Ann", ["Bob", "Cy"])).toBe("Ann sent a note to Bob, Cy");
	});

	it("falls back to the author's note when nobody is named", () => {
		expect(noteStubText("Ann", [])).toBe("Ann's note");
	});

	it("doesn't need an author", () => {
		expect(noteStubText(null, ["Bob"])).toBe("Someone sent a note to Bob");
	});
});
