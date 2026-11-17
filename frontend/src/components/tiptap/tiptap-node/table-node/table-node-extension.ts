import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { closestNode } from "#/components/tiptap/tiptap-extension/closest-node";

// The v1 `[table]` flags that survive the port. v1's `center` and `right` aligned the
// text in the cells, so they become one `align` choice. `ht`, `hl`, and `htl` (a
// dark first row, first column, or both) become one `header` choice. `stats` was a
// header row plus right-aligned cells, which is those two choices together, so it
// is not a flag of its own. `dnd5e` (a character-sheet look) and `rolls`, `d20`,
// and `pool` (which needed the old sheet's JavaScript) are dropped.
export const TABLE_HEADERS = [
	{ key: "none", label: "No header" },
	{ key: "row", label: "Header row" },
	{ key: "column", label: "Header column" },
	{ key: "both", label: "Header row and column" },
] as const;

export const TABLE_ALIGNS = [
	{ key: "left", label: "Align left" },
	{ key: "center", label: "Align center" },
	{ key: "right", label: "Align right" },
] as const;

export const TABLE_FLAGS = [
	{ key: "compact", label: "Compact" },
	{ key: "grid", label: "Grid lines" },
	{ key: "zebra", label: "Striped rows" },
] as const;

export type TableHeaderKey = (typeof TABLE_HEADERS)[number]["key"];
export type TableAlignKey = (typeof TABLE_ALIGNS)[number]["key"];
export type TableFlagKey = (typeof TABLE_FLAGS)[number]["key"];

const HEADER_KEYS: ReadonlySet<unknown> = new Set(TABLE_HEADERS.map((h) => h.key));
const ALIGN_KEYS: ReadonlySet<unknown> = new Set(TABLE_ALIGNS.map((a) => a.key));

export function isTableHeaderKey(value: unknown): value is TableHeaderKey {
	return HEADER_KEYS.has(value);
}

export function isTableAlignKey(value: unknown): value is TableAlignKey {
	return ALIGN_KEYS.has(value);
}

export type TableStyle = {
	compact: boolean;
	grid: boolean;
	zebra: boolean;
	header: TableHeaderKey;
	align: TableAlignKey;
};

export const TABLE_NODE_NAME = "table";

// Every `data-*` attribute the table can carry.
const TABLE_DATA_ATTRIBUTES = [
	"data-compact",
	"data-grid",
	"data-zebra",
	"data-header",
	"data-align",
] as const;

// The attributes a table is rendered with. Only allowlisted values get through, and
// a default renders as nothing, so a stored unknown value is a plain table.
export function tableDataAttributes(
	attrs: Record<string, unknown>,
): Record<string, string> {
	const out: Record<string, string> = {};
	if (attrs["compact"] === true) out["data-compact"] = "true";
	if (attrs["grid"] === true) out["data-grid"] = "true";
	if (attrs["zebra"] === true) out["data-zebra"] = "true";
	if (isTableHeaderKey(attrs["header"]) && attrs["header"] !== "none") {
		out["data-header"] = attrs["header"];
	}
	if (isTableAlignKey(attrs["align"]) && attrs["align"] !== "left") {
		out["data-align"] = attrs["align"];
	}
	return out;
}

// A boolean flag, read from `data-<key>` or from the v1 markup's class.
function flagAttribute(key: TableFlagKey, legacyClass: string) {
	const name = `data-${key}`;
	return {
		default: false,
		parseHTML: (element: HTMLElement) =>
			element.getAttribute(name) === "true" || element.classList.contains(legacyClass),
		renderHTML: (attributes: Record<string, unknown>) => {
			const value = tableDataAttributes(attributes)[name];
			return value === undefined ? {} : { [name]: value };
		},
	};
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		tableStyle: {
			/** Change the style choices of the table the selection is in. */
			setTableStyle: (style: Partial<TableStyle>) => ReturnType;
			/**
			 * Insert a 3x3 table at the cursor (with the first row as a header unless
			 * `style` says otherwise). Does nothing inside a table.
			 */
			insertStyledTable: (style?: Partial<TableStyle>) => ReturnType;
		};
	}
}

function validStyle(style: Partial<TableStyle>): boolean {
	return (
		(style.compact === undefined || typeof style.compact === "boolean") &&
		(style.grid === undefined || typeof style.grid === "boolean") &&
		(style.zebra === undefined || typeof style.zebra === "boolean") &&
		(style.header === undefined || isTableHeaderKey(style.header)) &&
		(style.align === undefined || isTableAlignKey(style.align))
	);
}

// The table's wrapper and `<table>` for the editor. Plain `renderHTML` can't be used
// there because Tiptap's stock node view writes a computed inline `style` and a
// `colgroup`; this one carries only the `data-*` attributes, in the same structure
// `renderHTML` produces, so the editor and the read-only content match.
class SafeTableView {
	dom: HTMLElement;
	contentDOM: HTMLElement;
	private table: HTMLElement;
	private node: ProseMirrorNode;

	constructor(node: ProseMirrorNode) {
		this.node = node;
		this.dom = document.createElement("div");
		this.dom.className = "tableWrapper";
		this.table = this.dom.appendChild(document.createElement("table"));
		this.contentDOM = this.table.appendChild(document.createElement("tbody"));
		this.applyAttributes();
	}

	private applyAttributes() {
		for (const name of TABLE_DATA_ATTRIBUTES) this.table.removeAttribute(name);
		for (const [name, value] of Object.entries(tableDataAttributes(this.node.attrs))) {
			this.table.setAttribute(name, value);
		}
	}

	update(node: ProseMirrorNode) {
		if (node.type !== this.node.type) return false;
		this.node = node;
		this.applyAttributes();
		return true;
	}

	ignoreMutation(mutation: MutationRecord | { type: "selection"; target: Node }) {
		const target = mutation.target;
		return (
			mutation.type !== "selection" &&
			this.dom.contains(target) &&
			!this.contentDOM.contains(target)
		);
	}
}

// Cells hold paragraphs only (no nested tables or columns, and a post's tables are
// small). Cell-level alignment, widths, and the like are not part of the model, so
// those attributes are neutralized: Tiptap's stock `align` renders an inline style
// from a stored value unchecked.
const unusedAttribute = {
	default: null,
	parseHTML: () => null,
	renderHTML: () => ({}),
};

export const GpTableCell = TableCell.extend({
	content: "paragraph+",
	addAttributes() {
		return {
			...this.parent?.(),
			colwidth: unusedAttribute,
			align: unusedAttribute,
		};
	},
});

// Header cells aren't made by the toolbar (the `header` choice styles the first row
// or column); this is for `<th>` cells in pasted tables.
export const GpTableHeader = TableHeader.extend({
	content: "paragraph+",
	addAttributes() {
		return {
			...this.parent?.(),
			colwidth: unusedAttribute,
			align: unusedAttribute,
		};
	},
});

// A table. Parsing reads `data-*` attributes and, for v1 posts, the `bbTable*`
// classes the v1 renderer emitted, and nothing else: never inline styles or widths.
// The wrapper (`div.tableWrapper`) is what scrolls sideways on a narrow screen.
export const GpTable = Table.extend({
	// `resizable` stays at Tiptap's default of false: no column resizing.
	addAttributes() {
		return {
			compact: flagAttribute("compact", "bbTableCompact"),
			grid: flagAttribute("grid", "bbTableGrid"),
			zebra: flagAttribute("zebra", "bbTableZebra"),
			header: {
				default: "none",
				parseHTML: (element: HTMLElement) => {
					const data = element.getAttribute("data-header");
					if (isTableHeaderKey(data)) return data;
					if (element.classList.contains("bbTable-htl")) return "both";
					if (
						element.classList.contains("bbTable-ht") ||
						element.classList.contains("bbTableStats")
					) {
						return "row";
					}
					if (element.classList.contains("bbTable-hl")) return "column";
					return "none";
				},
				renderHTML: (attributes: Record<string, unknown>) => {
					const value = tableDataAttributes(attributes)["data-header"];
					return value === undefined ? {} : { "data-header": value };
				},
			},
			align: {
				default: "left",
				parseHTML: (element: HTMLElement) => {
					const data = element.getAttribute("data-align");
					if (isTableAlignKey(data)) return data;
					if (element.classList.contains("bbTableCenter")) return "center";
					if (
						element.classList.contains("bbTableRight") ||
						element.classList.contains("bbTableStats")
					) {
						return "right";
					}
					return "left";
				},
				renderHTML: (attributes: Record<string, unknown>) => {
					const value = tableDataAttributes(attributes)["data-align"];
					return value === undefined ? {} : { "data-align": value };
				},
			},
		};
	},

	renderHTML({ HTMLAttributes }) {
		return ["div", { class: "tableWrapper" }, ["table", HTMLAttributes, ["tbody", 0]]];
	},

	addNodeView() {
		return ({ node }) => new SafeTableView(node);
	},

	addCommands() {
		return {
			...this.parent?.(),

			setTableStyle:
				(style) =>
				({ state, tr, dispatch }) => {
					if (!validStyle(style)) return false;
					const found = closestNode(state, TABLE_NODE_NAME);
					if (!found) return false;
					if (dispatch) {
						const changes: Partial<TableStyle> = {};
						for (const key of [
							"compact",
							"grid",
							"zebra",
							"header",
							"align",
						] as const) {
							if (style[key] !== undefined)
								Object.assign(changes, { [key]: style[key] });
						}
						tr.setNodeMarkup(found.pos, undefined, { ...found.node.attrs, ...changes });
					}
					return true;
				},

			insertStyledTable:
				(style = {}) =>
				({ state, chain }) => {
					if (!validStyle(style)) return false;
					if (closestNode(state, TABLE_NODE_NAME)) return false;
					return chain()
						.insertTable({ rows: 3, cols: 3, withHeaderRow: false })
						.setTableStyle({ header: "row", ...style })
						.run();
				},
		};
	},
});

// The table nodes together, for both the editor and the read-only renderer.
export const TABLE_EXTENSIONS = [GpTable, TableRow, GpTableCell, GpTableHeader];
