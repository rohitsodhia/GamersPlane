import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { Column, Columns } from "./columns-node-extension";

const extensions = [StarterKit, Columns, Column];

const para = (text: string): JSONContent => ({
	type: "paragraph",
	content: [{ type: "text", text }],
});
const column = (...texts: string[]): JSONContent => ({
	type: "column",
	content: texts.map(para),
});
const columnsDoc = (count: unknown, columns: JSONContent[]): JSONContent => ({
	type: "doc",
	content: [{ type: "columns", attrs: { count }, content: columns }],
});

const parse = (html: string): JSONContent => generateJSON(html, extensions);
const columnTexts = (doc: JSONContent) =>
	doc.content?.[0]?.content?.map((col) =>
		col.content?.map((p) => p.content?.[0]?.text).join("|"),
	);

describe("columns node", () => {
	it("round-trips three columns as data attributes", () => {
		const columns = [column("c0"), column("c1"), column("c2")];
		const html = generateHTML(columnsDoc(3, columns), extensions);
		expect(html).toContain('data-type="columns"');
		expect(html).toContain('data-count="3"');
		expect(html).not.toContain("style=");
		const doc = parse(html);
		expect(doc.content?.[0]?.attrs).toEqual({ count: 3 });
		expect(columnTexts(doc)).toEqual(["c0", "c1", "c2"]);
	});

	it("renders an unknown count without a data-count, without throwing", () => {
		const html = generateHTML(columnsDoc(9, [column("a"), column("b")]), extensions);
		expect(html).not.toContain("data-count");
		expect(html).toContain('data-type="column"');
	});

	it("reads a hostile pasted count as the number of columns", () => {
		const doc = parse(
			'<div data-type="columns" data-count="99"><div data-type="column"><p>a</p></div><div data-type="column"><p>b</p></div></div>',
		);
		expect(doc.content?.[0]?.attrs).toEqual({ count: 2 });
		// With no usable count or class, the number of columns decides.
		const three = parse(
			'<div data-type="columns" data-count="99"><div data-type="column"><p>a</p></div><div data-type="column"><p>b</p></div><div data-type="column"><p>c</p></div></div>',
		);
		expect(three.content?.[0]?.attrs).toEqual({ count: 3 });
	});

	it("reads the v1 renderer's layout classes", () => {
		const doc = parse(
			'<div class="layout-columns-3"><div class="layout-column"><p>a</p></div><div class="layout-column"><p>b</p></div><div class="layout-column"><p>c</p></div></div>',
		);
		expect(doc.content?.[0]?.type).toBe("columns");
		expect(doc.content?.[0]?.attrs).toEqual({ count: 3 });
		expect(columnTexts(doc)).toEqual(["a", "b", "c"]);
		const two = parse(
			'<div class="layout-columns-2"><div class="layout-column"><p>a</p></div><div class="layout-column"><p>b</p></div></div>',
		);
		expect(two.content?.[0]?.attrs).toEqual({ count: 2 });
	});
});

describe("columns commands", () => {
	const makeEditor = (content: JSONContent) => new Editor({ extensions, content });
	const types = (editor: Editor) => editor.getJSON().content?.map((node) => node.type);
	const threeColumns = () =>
		columnsDoc(3, [column("one", "one b"), column("two"), column("three")]);

	it("setColumns inserts empty columns, and a document ending in them has a place to type", () => {
		const editor = makeEditor({ type: "doc", content: [{ type: "paragraph" }] });
		expect(editor.commands.setColumns(3)).toBe(true);
		const json = editor.getJSON();
		expect(json.content?.[0]?.type).toBe("columns");
		expect(json.content?.[0]?.attrs).toEqual({ count: 3 });
		expect(json.content?.[0]?.content).toHaveLength(3);
		// StarterKit's trailing node: the cursor can leave the columns.
		expect(types(editor)?.at(-1)).toBe("paragraph");
		editor.destroy();
	});

	it("setColumns inside columns changes the count instead of nesting", () => {
		const editor = makeEditor(columnsDoc(2, [column("a"), column("b")]));
		editor.commands.setTextSelection(3);
		expect(editor.commands.setColumns(3)).toBe(true);
		expect(editor.getJSON().content?.[0]?.attrs).toEqual({ count: 3 });
		expect(editor.getJSON().content?.[0]?.content).toHaveLength(3);
		editor.destroy();
	});

	it("growing adds empty columns at the end and keeps the rest", () => {
		const editor = makeEditor(columnsDoc(2, [column("a"), column("b")]));
		editor.commands.setTextSelection(3);
		editor.commands.setColumnCount(3);
		const doc = editor.getJSON();
		expect(columnTexts(doc)).toEqual(["a", "b", ""]);
		editor.destroy();
	});

	it("reducing merges the removed columns' content into the last one kept", () => {
		const editor = makeEditor(threeColumns());
		editor.commands.setTextSelection(3);
		expect(editor.commands.setColumnCount(2)).toBe(true);
		const doc = editor.getJSON();
		expect(doc.content?.[0]?.attrs).toEqual({ count: 2 });
		expect(columnTexts(doc)).toEqual(["one|one b", "two|three"]);
		editor.destroy();
	});

	it("refuses a bad count, and does nothing outside columns", () => {
		const editor = makeEditor(threeColumns());
		// @ts-expect-error not an allowed count
		expect(editor.commands.setColumns(4)).toBe(false);
		editor.commands.setTextSelection(editor.state.doc.content.size);
		expect(editor.commands.setColumnCount(2)).toBe(false);
		expect(editor.commands.unsetColumns()).toBe(false);
		editor.destroy();
	});

	it("unsetColumns keeps every column's content as consecutive blocks", () => {
		const editor = makeEditor(threeColumns());
		editor.commands.setTextSelection(3);
		expect(editor.commands.unsetColumns()).toBe(true);
		const json: JSONContent = editor.getJSON();
		expect(json.content?.map((n) => n.content?.[0]?.text)).toEqual([
			"one",
			"one b",
			"two",
			"three",
			undefined, // StarterKit's trailing paragraph
		]);
		editor.destroy();
	});

	it("never nests: columns inside a column are flattened into its blocks", () => {
		const inner: JSONContent = {
			type: "columns",
			attrs: { count: 2 },
			content: [column("in a"), column("in b")],
		};
		const editor = makeEditor({
			type: "doc",
			content: [
				{
					type: "columns",
					attrs: { count: 2 },
					content: [
						{ type: "column", content: [para("out a"), inner] },
						column("out b"),
					],
				},
			],
		});
		// The guard runs on a transaction; make one.
		editor.commands.insertContentAt(editor.state.doc.content.size - 1, " ");
		const json: JSONContent = editor.getJSON();
		const outer = json.content?.[0];
		expect(outer?.content?.[0]?.content?.map((n) => n.type)).toEqual([
			"paragraph",
			"paragraph",
			"paragraph",
		]);
		let nested = 0;
		editor.state.doc.descendants((node, pos) => {
			if (node.type.name === "columns" && pos > 0) nested++;
		});
		expect(nested).toBe(0);
		editor.destroy();
	});

	it("keeps count equal to the number of columns for a stored mismatch", () => {
		const editor = makeEditor(columnsDoc(3, [column("a"), column("b")]));
		editor.commands.setTextSelection(3);
		editor.commands.insertContent("x");
		expect(editor.getJSON().content?.[0]?.attrs).toEqual({ count: 2 });
		editor.destroy();
	});
});
