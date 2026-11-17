import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { Color } from "@tiptap/extension-color";
import { TextStyle } from "@tiptap/extension-text-style";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { FONT_FAMILIES, FontFamily } from "./font-family-extension";
import { FONT_SIZES, FontSize } from "./font-size-extension";
import {
	highlightTextColor,
	SafeHighlight,
	safeHighlightColor,
} from "./highlight-extension";
import { SafeOrderedList } from "./ordered-list-extension";

const extensions = [
	StarterKit.configure({ orderedList: false }),
	SafeOrderedList,
	TextStyle,
	Color,
	SafeHighlight,
	FontSize,
	FontFamily,
];

const paragraphOf = (marks: { type: string; attrs?: object }[]): JSONContent => ({
	type: "doc",
	content: [{ type: "paragraph", content: [{ type: "text", text: "hi", marks }] }],
});
const marksOf = (doc: JSONContent) => doc.content?.[0]?.content?.[0]?.marks ?? [];
const parse = (html: string) => generateJSON(html, extensions);

// Each mark stores a preset key and renders it as one data attribute.
const presetMarks = [
	{ mark: "fontSize", attr: "size", data: "data-font-size", valid: "gargantuan" },
	{ mark: "fontFamily", attr: "font", data: "data-font", valid: "eagle" },
] as const;

describe.each(presetMarks)("$mark mark", ({ mark, attr, data, valid }) => {
	it("round-trips a preset key through HTML and back, beside bold and color", () => {
		const doc = paragraphOf([
			{ type: "bold" },
			{ type: "textStyle", attrs: { color: "#ff0000" } },
			{ type: mark, attrs: { [attr]: valid } },
		]);
		const html = generateHTML(doc, extensions);
		expect(html).toContain(`${data}="${valid}"`);
		expect(html).not.toMatch(/style="[^"]*font-(size|family)/);
		const types = marksOf(parse(html)).map((m) => m.type);
		expect(types).toEqual(expect.arrayContaining(["bold", "textStyle", mark]));
		expect(marksOf(parse(html)).find((m) => m.type === mark)?.attrs?.[attr]).toBe(
			valid,
		);
	});

	it.each([
		["an unknown key", "comic-sans"],
		["a non-string", { raw: "10px" }],
	])("renders %s as plain text without throwing", (_name, bad) => {
		const html = generateHTML(
			paragraphOf([{ type: mark, attrs: { [attr]: bad } }]),
			extensions,
		);
		expect(html).not.toContain(data);
		expect(html).toContain("hi");
	});

	it("ignores a span whose data attribute is not an allowlisted key", () => {
		const doc = parse(`<p><span ${data}="expression(alert(1))">hi</span></p>`);
		expect(marksOf(doc).map((m) => m.type)).not.toContain(mark);
	});
});

describe("pasted inline styles", () => {
	it("never become a font size or font family mark", () => {
		const doc = parse(
			'<p><span style="font-size: 99px; font-family: Impact; color: red">hi</span></p>',
		);
		const types = marksOf(doc).map((m) => m.type);
		expect(types).not.toContain("fontSize");
		expect(types).not.toContain("fontFamily");
		// The existing color mark still reads the color, as before.
		expect(marksOf(doc).find((m) => m.type === "textStyle")?.attrs?.["color"]).toBe(
			"red",
		);
	});
});

describe("preset lists", () => {
	const scss = readFileSync(join(import.meta.dirname, "text-format.scss"), "utf8");

	it("has a stylesheet rule for every size and font key", () => {
		for (const { key } of [...FONT_SIZES, ...FONT_FAMILIES]) {
			expect(scss).toMatch(new RegExp(`^\\s*["']${key}["']\\s*:`, "m"));
		}
	});
});

describe("highlight mark", () => {
	it("keeps plain hex and named colors and rejects anything that could break out of the style", () => {
		expect(safeHighlightColor("#FFFF00")).toBe("#FFFF00");
		expect(safeHighlightColor("yellow")).toBe("yellow");
		expect(safeHighlightColor("red; background: url(x)")).toBeNull();
		expect(safeHighlightColor("url(javascript:1)")).toBeNull();
		expect(safeHighlightColor(12)).toBeNull();
	});

	it("picks readable text for the background", () => {
		expect(highlightTextColor("#000000")).toBe("#ffffff");
		expect(highlightTextColor("#ffff00")).toBe("#000000");
		expect(highlightTextColor("#fff")).toBe("#000000");
		expect(highlightTextColor("yellow")).toBe("inherit");
	});

	it("round-trips a color and drops an unsafe one", () => {
		const good = generateHTML(
			paragraphOf([{ type: "highlight", attrs: { color: "#c0c0c0" } }]),
			extensions,
		);
		expect(good).toContain('data-color="#c0c0c0"');
		expect(
			marksOf(parse(good)).find((m) => m.type === "highlight")?.attrs?.["color"],
		).toBe("#c0c0c0");

		const bad = generateHTML(
			paragraphOf([{ type: "highlight", attrs: { color: "red; x: y" } }]),
			extensions,
		);
		expect(bad).not.toContain("red; x: y");
	});

	it("does not read a pasted inline background", () => {
		const doc: JSONContent = parse(
			'<p><mark style="background-color: red">a</mark><span style="background-color: blue">b</span></p>',
		);
		const colors = doc.content?.[0]?.content?.flatMap((n) =>
			(n.marks ?? [])
				.filter((m) => m.type === "highlight")
				.map((m) => m.attrs?.["color"]),
		);
		expect(colors).toEqual([null]);
	});
});

describe("ordered list start and type", () => {
	const list = (attrs: object): JSONContent => ({
		type: "doc",
		content: [
			{
				type: "orderedList",
				attrs,
				content: [
					{
						type: "listItem",
						content: [{ type: "paragraph", content: [{ type: "text", text: "x" }] }],
					},
				],
			},
		],
	});

	it("renders start and type and reads them back", () => {
		const html = generateHTML(list({ start: 4, type: "a" }), extensions);
		expect(html).toContain('<ol start="4" type="a">');
		expect(parse(html).content?.[0]?.attrs).toEqual({ start: 4, type: "a" });
	});

	it("falls back to a plain list for a bad start or type", () => {
		expect(generateHTML(list({ start: Number.NaN, type: "z" }), extensions)).toContain(
			"<ol>",
		);
		expect(generateHTML(list({ start: -2, type: { x: 1 } }), extensions)).toContain(
			"<ol>",
		);
		expect(
			parse('<ol start="abc" type="roman"><li><p>x</p></li></ol>').content?.[0]?.attrs,
		).toEqual({ start: 1, type: null });
	});
});

// The toolbar drives the marks through these commands, so they must exist on a
// real editor and set the same mark the document renders.
describe("preset commands", () => {
	it("setFontSizePreset and setFontFamilyPreset apply to the selection", () => {
		const editor = new Editor({ extensions, content: "<p>hi</p>" });
		editor
			.chain()
			.selectAll()
			.setFontSizePreset("huge")
			.setFontFamilyPreset("eagle")
			.run();
		expect(marksOf(editor.getJSON())).toEqual([
			{ type: "fontSize", attrs: { size: "huge" } },
			{ type: "fontFamily", attrs: { font: "eagle" } },
		]);
		editor.chain().selectAll().unsetFontSizePreset().unsetFontFamilyPreset().run();
		expect(marksOf(editor.getJSON())).toEqual([]);
		editor.destroy();
	});

	it("a size or font picked at an empty cursor carries on past the first character", () => {
		const editor = new Editor({ extensions, content: "<p></p>" });
		editor.chain().focus().setFontSizePreset("huge").setFontFamilyPreset("eagle").run();
		for (const char of "abc") editor.commands.insertContent(char);
		const text: JSONContent[] = editor.getJSON().content?.[0]?.content ?? [];
		expect(text.map((node) => node.text).join("")).toBe("abc");
		for (const node of text) {
			expect(node.marks).toEqual([
				{ type: "fontSize", attrs: { size: "huge" } },
				{ type: "fontFamily", attrs: { font: "eagle" } },
			]);
		}
		editor.destroy();
	});

	it("a text color shows on highlighted text (the highlight wraps the color)", () => {
		const html = generateHTML(
			paragraphOf([
				{ type: "highlight", attrs: { color: "#ffff00" } },
				{ type: "textStyle", attrs: { color: "#ff0000" } },
			]),
			extensions,
		);
		expect(html).toMatch(
			/<mark [^>]*><span style="color: rgb\(255, 0, 0\);">hi<\/span><\/mark>/,
		);
	});

	it("a color or highlight picked at an empty cursor carries on past the first character", () => {
		const editor = new Editor({ extensions, content: "<p></p>" });
		editor.chain().focus().setColor("#ff0000").setHighlight({ color: "#ffff00" }).run();
		for (const char of "abc") editor.commands.insertContent(char);
		const text: JSONContent[] = editor.getJSON().content?.[0]?.content ?? [];
		expect(text.map((node) => node.text).join("")).toBe("abc");
		for (const node of text) {
			expect(node.marks).toEqual(
				expect.arrayContaining([
					{ type: "textStyle", attrs: expect.objectContaining({ color: "#ff0000" }) },
					{ type: "highlight", attrs: { color: "#ffff00" } },
				]),
			);
		}
		editor.destroy();
	});
});
