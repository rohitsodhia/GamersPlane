import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { FloatImage } from "#/components/tiptap/tiptap-extension/image-extension";
import { BOX_VARIANTS, Box } from "./box-node-extension";

const extensions = [StarterKit, Box, FloatImage];

const boxDoc = (attrs: object): JSONContent => ({
	type: "doc",
	content: [
		{
			type: "box",
			attrs,
			content: [{ type: "paragraph", content: [{ type: "text", text: "hi" }] }],
		},
	],
});
const firstAttrs = (doc: JSONContent) => doc.content?.[0]?.attrs;
const parse = (html: string): JSONContent => generateJSON(html, extensions);

describe("box node", () => {
	it.each(
		BOX_VARIANTS.flatMap((v) =>
			(["none", "left", "right"] as const).map((f) => [v.key, f] as const),
		),
	)("round-trips variant %s with float %s as data attributes", (variant, float) => {
		const html = generateHTML(boxDoc({ variant, float }), extensions);
		expect(html).toContain('data-type="box"');
		expect(html).toContain(`data-variant="${variant}"`);
		expect(html).not.toContain("style=");
		if (float === "none") expect(html).not.toContain("data-float");
		else expect(html).toContain(`data-float="${float}"`);
		expect(firstAttrs(parse(html))).toEqual({ variant, float });
	});

	it("renders an unknown or wrong-typed variant and float without a look, without throwing", () => {
		for (const attrs of [
			{ variant: "comic-sans", float: "centre" },
			{ variant: { raw: 1 }, float: 7 },
		]) {
			const html = generateHTML(boxDoc(attrs), extensions);
			expect(html).toContain('data-type="box"');
			expect(html).not.toContain("data-variant");
			expect(html).not.toContain("data-float");
			expect(html).toContain("hi");
		}
	});

	it("reads an unknown pasted data-variant as a plain box and a missing one as the default", () => {
		expect(
			firstAttrs(
				parse('<div data-type="box" data-variant="evil" data-float="x"><p>a</p></div>'),
			),
		).toEqual({ variant: "", float: "none" });
		expect(firstAttrs(parse('<div data-type="box"><p>a</p></div>'))).toEqual({
			variant: "border",
			float: "none",
		});
	});
});

describe("box commands", () => {
	const makeEditor = (content: string) => new Editor({ extensions, content });
	const types = (editor: Editor) => editor.getJSON().content?.map((node) => node.type);

	it("setBox wraps the selected blocks, and again changes that box instead of nesting", () => {
		const editor = makeEditor("<p>one</p><p>two</p>");
		editor.chain().selectAll().setBox({ variant: "paper" }).run();
		// StarterKit's trailing node adds the paragraph after a document-final box.
		expect(types(editor)).toEqual(["box", "paragraph"]);
		expect(editor.getJSON().content?.[0]?.content).toHaveLength(2);

		editor.chain().selectAll().setBox({ variant: "terminal", float: "right" }).run();
		expect(types(editor)).toEqual(["box", "paragraph"]);
		expect(firstAttrs(editor.getJSON())).toEqual({
			variant: "terminal",
			float: "right",
		});
		expect(editor.getJSON().content?.[0]?.content?.map((n) => n.type)).toEqual([
			"paragraph",
			"paragraph",
		]);
		editor.destroy();
	});

	it("setBox at an empty cursor inserts an empty box with a paragraph", () => {
		const editor = makeEditor("<p></p>");
		editor.chain().focus().setBox({ variant: "parchment" }).run();
		const box = editor.getJSON().content?.[0];
		expect(box?.type).toBe("box");
		expect(box?.attrs?.["variant"]).toBe("parchment");
		expect(box?.content?.[0]?.type).toBe("paragraph");
		editor.destroy();
	});

	it("updateBox changes only the attributes given, and refuses bad keys", () => {
		const editor = makeEditor(
			'<div data-type="box" data-variant="paper"><p>x</p></div>',
		);
		editor.commands.setTextSelection(2);
		expect(editor.commands.updateBox({ float: "left" })).toBe(true);
		expect(firstAttrs(editor.getJSON())).toEqual({ variant: "paper", float: "left" });
		// @ts-expect-error a key that isn't allowlisted
		expect(editor.commands.updateBox({ variant: "gold" })).toBe(false);
		expect(firstAttrs(editor.getJSON())).toEqual({ variant: "paper", float: "left" });
		editor.destroy();
	});

	it("unsetBox lifts the content back out, and does nothing outside a box", () => {
		const editor = makeEditor(
			'<p>before</p><div data-type="box"><p>a</p><p>b</p></div>',
		);
		editor.commands.setTextSelection(1);
		expect(editor.commands.unsetBox()).toBe(false);
		editor.commands.setTextSelection(10); // inside the box's first paragraph
		expect(editor.commands.unsetBox()).toBe(true);
		// Before, the box's two, and the trailing paragraph StarterKit added after it.
		expect(types(editor)).toEqual(["paragraph", "paragraph", "paragraph", "paragraph"]);
		editor.destroy();
	});

	it("unwraps a box that arrives inside another box (such as a paste)", () => {
		const editor = makeEditor("<p>x</p>");
		editor.commands.insertContent({
			type: "box",
			content: [
				{
					type: "box",
					content: [{ type: "paragraph", content: [{ type: "text", text: "in" }] }],
				},
			],
		});
		const outer = editor.getJSON().content?.find((node) => node.type === "box");
		expect(outer?.content?.map((node) => node.type)).toEqual(["paragraph"]);
		editor.destroy();
	});
});

describe("image float", () => {
	const image = (float: unknown): JSONContent => ({
		type: "doc",
		content: [{ type: "image", attrs: { src: "https://example.com/a.png", float } }],
	});

	it.each(["left", "right"] as const)("round-trips float %s", (float) => {
		const html = generateHTML(image(float), extensions);
		expect(html).toContain(`data-float="${float}"`);
		expect(firstAttrs(parse(html))?.["float"]).toBe(float);
	});

	it("renders no float for none or a bad value, and reads a bad one as none", () => {
		for (const bad of ["none", "centre", 3]) {
			expect(generateHTML(image(bad), extensions)).not.toContain("data-float");
		}
		expect(
			firstAttrs(parse('<img src="https://example.com/a.png" data-float="evil">'))?.[
				"float"
			],
		).toBe("none");
	});

	it("setImageFloat sets the selected image's float", () => {
		const editor = new Editor({
			extensions,
			content: '<img src="https://example.com/a.png">',
		});
		editor.commands.setNodeSelection(0);
		expect(editor.commands.setImageFloat("right")).toBe(true);
		expect(firstAttrs(editor.getJSON())?.["float"]).toBe("right");
		editor.destroy();
	});
});
