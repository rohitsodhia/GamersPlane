import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { TABLE_EXTENSIONS } from "./table-node-extension";

const extensions = [StarterKit, ...TABLE_EXTENSIONS];

const cell = (text: string): JSONContent => ({
	type: "tableCell",
	content: [{ type: "paragraph", content: [{ type: "text", text }] }],
});

const tableDoc = (attrs: object): JSONContent => ({
	type: "doc",
	content: [
		{
			type: "table",
			attrs,
			content: [{ type: "tableRow", content: [cell("a"), cell("b")] }],
		},
	],
});

const firstAttrs = (doc: JSONContent) => doc.content?.[0]?.attrs;
const parse = (html: string): JSONContent => generateJSON(html, extensions);

describe("table node", () => {
	it("round-trips every style choice as data attributes inside a scroll wrapper", () => {
		const attrs = {
			compact: true,
			grid: true,
			zebra: true,
			header: "both",
			align: "right",
		};
		const html = generateHTML(tableDoc(attrs), extensions);
		expect(html.startsWith('<div class="tableWrapper"><table')).toBe(true);
		for (const name of [
			'data-compact="true"',
			'data-grid="true"',
			'data-zebra="true"',
			'data-header="both"',
			'data-align="right"',
		]) {
			expect(html).toContain(name);
		}
		expect(html).not.toContain("style=");
		expect(html).not.toContain("colgroup");
		expect(firstAttrs(parse(html))).toEqual(attrs);
	});

	it("renders defaults as a plain table", () => {
		const html = generateHTML(
			tableDoc({
				compact: false,
				grid: false,
				zebra: false,
				header: "none",
				align: "left",
			}),
			extensions,
		);
		expect(html).not.toContain("data-");
	});

	it("renders unknown or wrong-typed values without a look, without throwing", () => {
		const html = generateHTML(
			tableDoc({
				compact: "true",
				grid: 1,
				header: "sideways",
				align: "left; background: url(//evil)",
			}),
			extensions,
		);
		expect(html).not.toContain("data-");
		expect(html).not.toContain("evil");
		expect(html).toContain("<td");
	});

	it("reads unknown pasted values as defaults and ignores inline styles and widths", () => {
		const doc = parse(
			'<table data-header="evil" data-align="up" data-grid="yes" style="width: 900px"><tr><td align="center" style="text-align: right" colwidth="500">x</td></tr></table>',
		);
		expect(firstAttrs(doc)).toEqual({
			compact: false,
			grid: false,
			zebra: false,
			header: "none",
			align: "left",
		});
		const html = generateHTML(doc, extensions);
		expect(html).not.toContain("style=");
		expect(html).not.toContain("500");
		expect(html).not.toContain("text-align");
	});

	it("reads the v1 renderer's classes", () => {
		const v1 = (classes: string) =>
			firstAttrs(
				parse(
					`<div class='bbTableWrapper'><table class='bbTable ${classes}'><tr><td>a</td><td>b</td></tr></table></div>`,
				),
			);
		expect(v1("bbTableCompact bbTableGrid bbTableZebra")).toEqual({
			compact: true,
			grid: true,
			zebra: true,
			header: "none",
			align: "left",
		});
		expect(v1("bbTableCenter bbTable-hl")).toMatchObject({
			header: "column",
			align: "center",
		});
		expect(v1("bbTableRight bbTable-htl")).toMatchObject({
			header: "both",
			align: "right",
		});
		// v1's stats was a header row plus right-aligned cells.
		expect(v1("bbTableStats")).toMatchObject({ header: "row", align: "right" });
		expect(v1("bbTable-ht")).toMatchObject({ header: "row", align: "left" });
		expect(v1("bbTableRolls bbTableD20 bbTablePool")).toMatchObject({
			header: "none",
			align: "left",
		});
	});
});

describe("table commands", () => {
	const makeEditor = (content: string) => new Editor({ extensions, content });
	const types = (editor: Editor) => editor.getJSON().content?.map((node) => node.type);

	it("insertStyledTable adds a 3 x 3 table with a header row and a place to type after it", () => {
		const editor = makeEditor("<p></p>");
		expect(editor.commands.insertStyledTable()).toBe(true);
		const json: JSONContent = editor.getJSON();
		const table = json.content?.[0];
		expect(table?.type).toBe("table");
		expect(table?.attrs).toMatchObject({ header: "row" });
		expect(table?.content).toHaveLength(3);
		expect(table?.content?.[0]?.content).toHaveLength(3);
		// Not header cells: the header look is the table's `header` choice.
		expect(table?.content?.[0]?.content?.[0]?.type).toBe("tableCell");
		expect(types(editor)?.at(-1)).toBe("paragraph");
		editor.destroy();
	});

	it("insertStyledTable takes style overrides, and refuses an invalid one", () => {
		const editor = makeEditor("<p></p>");
		// @ts-expect-error not an allowlisted value
		expect(editor.commands.insertStyledTable({ header: "diagonal" })).toBe(false);
		expect(editor.getJSON().content?.[0]?.type).toBe("paragraph");
		expect(editor.commands.insertStyledTable({ header: "none", zebra: true })).toBe(
			true,
		);
		const json: JSONContent = editor.getJSON();
		expect(json.content?.[0]?.attrs).toMatchObject({ header: "none", zebra: true });
		editor.destroy();
	});

	it("insertStyledTable does nothing inside a table", () => {
		const editor = makeEditor("<table><tr><td>x</td></tr></table>");
		editor.commands.setTextSelection(4);
		expect(editor.commands.insertStyledTable()).toBe(false);
		editor.destroy();
	});

	it("setTableStyle changes only what is given, and refuses bad values or no table", () => {
		const editor = makeEditor("<p>out</p><table><tr><td>x</td></tr></table>");
		editor.commands.setTextSelection(1);
		expect(editor.commands.setTableStyle({ grid: true })).toBe(false);
		let inCell = 0;
		editor.state.doc.descendants((node, pos) => {
			if (node.isText && node.text === "x") inCell = pos + 1;
		});
		editor.commands.setTextSelection(inCell);
		expect(editor.commands.setTableStyle({ grid: true, align: "center" })).toBe(true);
		expect(editor.commands.setTableStyle({ header: "column" })).toBe(true);
		// @ts-expect-error not an allowlisted value
		expect(editor.commands.setTableStyle({ align: "justify" })).toBe(false);
		expect(editor.getJSON().content?.[1]?.attrs).toEqual({
			compact: false,
			grid: true,
			zebra: false,
			header: "column",
			align: "center",
		});
		editor.destroy();
	});

	it("builds the editor view with data attributes inside a scrolling wrapper", () => {
		const editor = makeEditor(
			'<table data-grid="true" data-header="row"><tr><td>x</td></tr></table>',
		);
		const wrapper = editor.view.dom.querySelector(".tableWrapper");
		const table = wrapper?.querySelector(":scope > table");
		expect(table?.getAttribute("data-grid")).toBe("true");
		expect(table?.getAttribute("data-header")).toBe("row");
		expect(table?.hasAttribute("style")).toBe(false);

		editor.commands.setTextSelection(4);
		editor.commands.setTableStyle({ grid: false, align: "center" });
		const after = editor.view.dom.querySelector(".tableWrapper > table");
		expect(after?.hasAttribute("data-grid")).toBe(false);
		expect(after?.getAttribute("data-align")).toBe("center");
		editor.destroy();
	});
});
