import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { Spoiler, spoilerTitle } from "./spoiler-node-extension";

// The React node view needs a mounted editor; commands and the HTML round trip don't.
const NoView = Spoiler.extend({ addNodeView: undefined as never });
const extensions = [StarterKit, NoView];

const spoilerDoc = (attrs: object): JSONContent => ({
	type: "doc",
	content: [
		{
			type: "spoiler",
			attrs,
			content: [{ type: "paragraph", content: [{ type: "text", text: "secret" }] }],
		},
	],
});
const parse = (html: string): JSONContent => generateJSON(html, extensions);
const first = (doc: JSONContent) => doc.content?.[0];

describe("spoiler node", () => {
	it("renders a details/summary with the title and round-trips through data-title", () => {
		const html = generateHTML(spoilerDoc({ title: "Plot twist" }), extensions);
		expect(html).toContain('data-type="spoiler"');
		expect(html).toContain('data-title="Plot twist"');
		expect(html).toContain("<summary>Plot twist</summary>");
		expect(html).not.toContain("open");
		expect(html).not.toContain("style=");
		expect(first(parse(html))?.type).toBe("spoiler");
		expect(first(parse(html))?.attrs).toEqual({ title: "Plot twist" });
	});

	it.each([
		["   ", "Spoiler"],
		[{ raw: 1 }, "Spoiler"],
		["  padded  ", "padded"],
		["x".repeat(500), "x".repeat(100)],
	])("reads the title %j as %j", (input, expected) => {
		expect(spoilerTitle(input)).toBe(expected);
		const html = generateHTML(spoilerDoc({ title: input }), extensions);
		expect(html).toContain(`<summary>${expected}</summary>`);
	});

	it.each([
		"blockquote",
		"div",
	])("reads v1's spoiler markup in a %s: title from the tag, content from the hidden div", (tag) => {
		const doc = parse(
			`<${tag} class="spoiler closed"><div class="tag">[ <span class="open">+</span>` +
				`<span class="close">-</span> ] Big reveal</div><div class="hidden"><p>secret</p></div></${tag}>`,
		);
		expect(doc.content).toHaveLength(1);
		expect(first(doc)?.type).toBe("spoiler");
		expect(first(doc)?.attrs).toEqual({ title: "Big reveal" });
		expect(first(doc)?.content?.[0]?.content?.[0]?.text).toBe("secret");
	});

	it("does not read v1's character sheet spoilers as spoilers", () => {
		const doc = parse(
			'<blockquote class="spoiler closed charsheet"><div class="tag">[ + ] Sheet</div>' +
				'<div class="hidden"><p>x</p></div></blockquote>',
		);
		expect(doc.content?.some((n) => n.type === "spoiler")).toBe(false);
	});
});

describe("spoiler commands", () => {
	const makeEditor = () => new Editor({ extensions, content: "<p>one</p><p>two</p>" });
	const types = (editor: Editor) => editor.getJSON().content?.map((n) => n.type);

	it("toggleSpoiler wraps the selection, and again unwraps the whole spoiler", () => {
		const editor = makeEditor();
		editor.chain().selectAll().toggleSpoiler().run();
		// (StarterKit's trailing node adds the empty paragraph after a final spoiler.)
		expect(types(editor)).toEqual(["spoiler", "paragraph"]);
		expect(first(editor.getJSON())?.attrs).toEqual({ title: "Spoiler" });
		expect(first(editor.getJSON())?.content).toHaveLength(2);

		// Caret in just one of the two paragraphs: both leave the spoiler.
		editor.commands.setTextSelection(3);
		editor.commands.toggleSpoiler();
		expect(types(editor)).toEqual(["paragraph", "paragraph", "paragraph"]);
		editor.destroy();
	});

	it("setSpoiler at an empty caret inserts an empty one with the given title", () => {
		const editor = makeEditor();
		editor.commands.setTextSelection(1);
		editor.commands.setSpoiler({ title: "Ending" });
		const spoiler = editor.getJSON().content?.find((n) => n.type === "spoiler");
		expect(spoiler?.attrs).toEqual({ title: "Ending" });
		editor.destroy();
	});

	it("unsetSpoiler reports false outside a spoiler", () => {
		const editor = makeEditor();
		expect(editor.commands.unsetSpoiler()).toBe(false);
		editor.destroy();
	});
});
