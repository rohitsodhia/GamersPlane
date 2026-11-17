import { mergeAttributes, Node } from "@tiptap/core";
import {
	Fragment,
	type NodeType,
	type Node as ProseMirrorNode,
} from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { closestNode } from "#/components/tiptap/tiptap-extension/closest-node";

// The v1 `[2column]` and `[3column]` containers holding `[col]` children. The
// document stores a `columns` node (with `count` 2 or 3) holding that many `column`
// nodes, each with block content. A document that ends in columns still has
// somewhere to type: StarterKit's trailing node adds an empty paragraph after it.
export const COLUMN_COUNTS = [2, 3] as const;
export type ColumnCount = (typeof COLUMN_COUNTS)[number];

export function isColumnCount(value: unknown): value is ColumnCount {
	return value === 2 || value === 3;
}

export const COLUMNS_NODE_NAME = "columns";
export const COLUMN_NODE_NAME = "column";

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		columns: {
			/**
			 * Insert a container of `count` empty columns at the cursor. Inside columns
			 * already, the count of that container is changed instead: columns never
			 * nest.
			 */
			setColumns: (count: ColumnCount) => ReturnType;
			/**
			 * Change the number of columns around the selection. More columns are added
			 * empty at the end; fewer fold the removed columns' content into the last
			 * one kept, so nothing is lost.
			 */
			setColumnCount: (count: ColumnCount) => ReturnType;
			/** Take the content out of the columns around the selection, as plain blocks. */
			unsetColumns: () => ReturnType;
		};
	}
}

function emptyColumn(type: NodeType): ProseMirrorNode {
	const column = type.createAndFill();
	if (!column) throw new Error("column must have default content");
	return column;
}

// The columns node with `count` columns, built from the existing ones.
function resized(
	node: ProseMirrorNode,
	count: ColumnCount,
	columnType: NodeType,
): ProseMirrorNode {
	const children: ProseMirrorNode[] = [];
	node.forEach((child) => {
		children.push(child);
	});
	let next = children.slice(0, count);
	if (children.length > count) {
		const last = next[next.length - 1] as ProseMirrorNode;
		let merged = last.content;
		for (const removed of children.slice(count))
			merged = merged.append(removed.content);
		next = [...next.slice(0, -1), last.copy(merged)];
	}
	while (next.length < count) next.push(emptyColumn(columnType));
	return node.type.create({ ...node.attrs, count }, next);
}

// The blocks inside every column of a columns node, in order.
function flattened(node: ProseMirrorNode): Fragment {
	let blocks = Fragment.empty;
	node.forEach((column) => {
		blocks = blocks.append(column.content);
	});
	return blocks;
}

const columnsGuardKey = new PluginKey("columnsGuard");

// `count` of a parsed container: how many `column` children the HTML has.
function parsedCount(element: HTMLElement): ColumnCount {
	const fromData = Number(element.getAttribute("data-count"));
	if (isColumnCount(fromData)) return fromData;
	if (element.classList.contains("layout-columns-3")) return 3;
	if (element.classList.contains("layout-columns-2")) return 2;
	const children = element.querySelectorAll(
		':scope > [data-type="column"], :scope > .layout-column',
	).length;
	return children >= 3 ? 3 : 2;
}

export const Column = Node.create({
	name: COLUMN_NODE_NAME,
	content: "block+",
	// Backspace at the start of a column must not merge it into the one before.
	isolating: true,
	defining: true,

	parseHTML() {
		return [
			{ tag: `div[data-type="${COLUMN_NODE_NAME}"]` },
			{ tag: "div.layout-column" },
		];
	},

	renderHTML({ HTMLAttributes }) {
		return [
			"div",
			mergeAttributes(HTMLAttributes, { "data-type": COLUMN_NODE_NAME }),
			0,
		];
	},
});

// A row of two or three columns. Rendered with plain `renderHTML` (no node view)
// so the editor and the read-only content produce identical markup. Parsing reads
// `div[data-type="columns"]` and the v1 `layout-columns-*` classes only.
export const Columns = Node.create({
	name: COLUMNS_NODE_NAME,
	group: "block",
	content: "column{2,3}",
	defining: true,

	addAttributes() {
		return {
			count: {
				default: 2,
				parseHTML: parsedCount,
				renderHTML: (attributes: Record<string, unknown>) =>
					isColumnCount(attributes["count"])
						? { "data-count": attributes["count"] }
						: {},
			},
		};
	},

	parseHTML() {
		return [
			{ tag: `div[data-type="${COLUMNS_NODE_NAME}"]` },
			{ tag: "div.layout-columns-2" },
			{ tag: "div.layout-columns-3" },
		];
	},

	renderHTML({ HTMLAttributes }) {
		return [
			"div",
			mergeAttributes(HTMLAttributes, { "data-type": COLUMNS_NODE_NAME }),
			0,
		];
	},

	addCommands() {
		return {
			setColumns:
				(count) =>
				({ state, commands }) => {
					if (!isColumnCount(count)) return false;
					if (closestNode(state, COLUMNS_NODE_NAME))
						return commands.setColumnCount(count);
					const columnType = state.schema.nodes[COLUMN_NODE_NAME];
					if (!columnType) return false;
					return commands.insertContent({
						type: this.name,
						attrs: { count },
						content: Array.from({ length: count }, () => ({
							type: COLUMN_NODE_NAME,
							content: [{ type: "paragraph" }],
						})),
					});
				},

			setColumnCount:
				(count) =>
				({ state, tr, dispatch }) => {
					if (!isColumnCount(count)) return false;
					const found = closestNode(state, COLUMNS_NODE_NAME);
					const columnType = state.schema.nodes[COLUMN_NODE_NAME];
					if (!found || !columnType) return false;
					if (dispatch) {
						tr.replaceWith(
							found.pos,
							found.pos + found.node.nodeSize,
							resized(found.node, count, columnType),
						);
					}
					return true;
				},

			unsetColumns:
				() =>
				({ state, tr, dispatch }) => {
					const found = closestNode(state, COLUMNS_NODE_NAME);
					if (!found) return false;
					if (dispatch) {
						tr.replaceWith(
							found.pos,
							found.pos + found.node.nodeSize,
							flattened(found.node),
						);
					}
					return true;
				},
		};
	},

	// Keeps stored documents consistent: a container inside another is flattened into
	// its blocks (columns never nest), and `count` always equals the number of columns.
	addProseMirrorPlugins() {
		return [
			new Plugin({
				key: columnsGuardKey,
				appendTransaction: (transactions, _oldState, newState) => {
					if (!transactions.some((transaction) => transaction.docChanged)) return null;
					const nested: { pos: number; node: ProseMirrorNode }[] = [];
					const miscounted: { pos: number; node: ProseMirrorNode }[] = [];
					newState.doc.descendants((node, pos) => {
						if (node.type.name !== COLUMNS_NODE_NAME) return;
						const $pos = newState.doc.resolve(pos);
						let inside = false;
						for (let depth = $pos.depth; depth > 0; depth--) {
							if ($pos.node(depth).type.name === COLUMNS_NODE_NAME) inside = true;
						}
						if (inside) {
							// Outermost only; a deeper one is handled by the next pass.
							const last = nested[nested.length - 1];
							if (!last || pos >= last.pos + last.node.nodeSize)
								nested.push({ pos, node });
						} else if (node.attrs["count"] !== node.childCount)
							miscounted.push({ pos, node });
					});
					if (nested.length === 0 && miscounted.length === 0) return null;
					const tr = newState.tr;
					// Back to front, so a change doesn't shift the positions still to do.
					const changes = [
						...nested.map((found) => ({ ...found, kind: "nested" as const })),
						...miscounted.map((found) => ({ ...found, kind: "count" as const })),
					].sort((a, b) => b.pos - a.pos);
					for (const { pos, node, kind } of changes) {
						if (kind === "nested") {
							tr.replaceWith(pos, pos + node.nodeSize, flattened(node));
						} else {
							tr.setNodeMarkup(pos, undefined, {
								...node.attrs,
								count: node.childCount,
							});
						}
					}
					return tr;
				},
			}),
		];
	},
});
