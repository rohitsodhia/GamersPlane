import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { contentHasPoll, Poll } from "./poll-node-extension";

const extensions = [StarterKit, Poll];
const para = (text: string): JSONContent => ({
	type: "paragraph",
	content: [{ type: "text", text }],
});
const pollCount = (editor: Editor) =>
	editor.getJSON().content?.filter((node) => node.type === "poll").length ?? 0;

describe("poll node", () => {
	it("renders an empty slot with no attributes and round-trips", () => {
		const doc: JSONContent = { type: "doc", content: [para("a"), { type: "poll" }] };
		const html = generateHTML(doc, extensions);
		expect(html).toContain('<div data-type="poll" class="poll-slot"></div>');
		const parsed = generateJSON(html, extensions);
		expect(parsed.content?.[1]).toEqual({ type: "poll" });
	});

	it("finds a poll marker anywhere in a document's JSON", () => {
		expect(contentHasPoll({ type: "doc", content: [para("a")] })).toBe(false);
		expect(
			contentHasPoll({ type: "doc", content: [para("a"), { type: "poll" }] }),
		).toBe(true);
		expect(contentHasPoll(undefined)).toBe(false);
		const nested: JSONContent = {
			type: "doc",
			content: [{ type: "box", content: [{ type: "poll" }] }],
		};
		expect(contentHasPoll(nested)).toBe(true);
	});
});

describe("poll commands", () => {
	it("inserts one marker and refuses a second", () => {
		const editor = new Editor({ extensions, content: "<p>one</p>" });
		expect(editor.commands.insertPoll()).toBe(true);
		expect(pollCount(editor)).toBe(1);
		expect(editor.commands.insertPoll()).toBe(false);
		expect(pollCount(editor)).toBe(1);
		editor.destroy();
	});

	it("removes extras that arrive another way, such as a paste", () => {
		const editor = new Editor({
			extensions,
			content: '<div data-type="poll"></div><p>mid</p>',
		});
		editor.commands.insertContentAt(editor.state.doc.content.size, [
			{ type: "poll" },
			{ type: "poll" },
		]);
		expect(pollCount(editor)).toBe(1);
		// The first one in the document is the one that stays.
		expect(editor.getJSON().content?.[0]?.type).toBe("poll");
		editor.destroy();
	});
});
