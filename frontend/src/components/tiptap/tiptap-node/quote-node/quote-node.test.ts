import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { Quote, quoteVariant } from "./quote-node-extension";

// The React node view needs a mounted editor; commands and the HTML round trip don't.
const NoView = Quote.extend({ addNodeView: undefined as never });
const extensions = [StarterKit, NoView];

const quoteDoc = (attrs: object): JSONContent => ({
	type: "doc",
	content: [
		{
			type: "quote",
			attrs,
			content: [{ type: "paragraph", content: [{ type: "text", text: "hi" }] }],
		},
	],
});
const parse = (html: string): JSONContent => generateJSON(html, extensions);
const first = (doc: JSONContent) => doc.content?.[0];

describe("quote variants", () => {
	it("renders ooc with a data attribute, an OOC label, and no quotee", () => {
		const html = generateHTML(quoteDoc({ variant: "ooc", quotee: "bob" }), extensions);
		expect(html).toContain('data-variant="ooc"');
		expect(html).toContain('class="quote ooc"');
		expect(html).toContain("OOC:");
		expect(html).not.toContain("bob");
		expect(html).not.toContain("style=");
		expect(first(parse(html))?.attrs).toEqual({ quotee: "", variant: "ooc" });
	});

	it("keeps a plain quote exactly as before (no variant attribute, quotee label)", () => {
		const html = generateHTML(quoteDoc({ quotee: "bob" }), extensions);
		expect(html).not.toContain("data-variant");
		expect(html).toContain("bob says:");
		expect(first(parse(html))?.attrs).toEqual({ quotee: "bob", variant: "quote" });
	});

	it("degrades an unknown or wrong-typed variant to a plain quote", () => {
		expect(quoteVariant({ raw: 1 })).toBe("quote");
		const html = generateHTML(quoteDoc({ variant: "evil" }), extensions);
		expect(html).not.toContain("data-variant");
		const pasted = parse(
			'<blockquote data-type="quote" data-variant="evil"><div class="quote-node-content"><p>x</p></div></blockquote>',
		);
		expect(first(pasted)?.attrs?.["variant"]).toBe("quote");
	});

	it("reads v1's oocText markup without its OOC label", () => {
		for (const tag of ["blockquote", "div"]) {
			const doc = parse(`<${tag} class="oocText"><div>OOC:</div><p>later</p></${tag}>`);
			expect(first(doc)?.type).toBe("quote");
			expect(first(doc)?.attrs?.["variant"]).toBe("ooc");
			expect(JSON.stringify(first(doc)?.content)).toContain("later");
			expect(JSON.stringify(first(doc)?.content)).not.toContain("OOC:");
		}
	});
});

describe("toggleOoc", () => {
	const makeEditor = (content: string) => new Editor({ extensions, content });
	const types = (editor: Editor) => editor.getJSON().content?.map((n) => n.type);

	it("wraps the selection in an OOC block, then takes all of it back out", () => {
		const editor = makeEditor("<p>one</p><p>two</p>");
		editor.chain().selectAll().toggleOoc().run();
		// (StarterKit's trailing node adds the empty paragraph after a final quote.)
		expect(types(editor)).toEqual(["quote", "paragraph"]);
		expect(first(editor.getJSON())?.attrs?.["variant"]).toBe("ooc");

		editor.commands.setTextSelection(3);
		editor.commands.toggleOoc();
		expect(types(editor)).toEqual(["paragraph", "paragraph", "paragraph"]);
	});

	it("turns a quote into an OOC block and drops its quotee", () => {
		const editor = makeEditor(
			'<blockquote data-type="quote" data-quotee="bob"><div class="quote-node-content"><p>hi</p></div></blockquote>',
		);
		editor.commands.setTextSelection(2);
		editor.commands.toggleOoc();
		expect(first(editor.getJSON())?.attrs).toEqual({ quotee: "", variant: "ooc" });
	});
});
