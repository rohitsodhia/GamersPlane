import { mergeAttributes, Node } from "@tiptap/core";
import { Fragment, type Node as ProseMirrorNode } from "@tiptap/pm/model";
import { type EditorState, Plugin, PluginKey } from "@tiptap/pm/state";
import {
	type FloatKey,
	floatAttribute,
	isFloatKey,
} from "#/components/tiptap/tiptap-extension/float-attribute";

// The v1 `[f=border]` and `[f=fancy-paper|parchment|vdu]` looks, as one node. The
// document stores the key only; what each key looks like is in box-node.scss, keyed
// on `data-variant`. "terminal" is v1's "vdu".
export const BOX_VARIANTS = [
	{ key: "border", label: "Border" },
	{ key: "paper", label: "Paper" },
	{ key: "parchment", label: "Parchment" },
	{ key: "terminal", label: "Terminal" },
] as const;

export type BoxVariantKey = (typeof BOX_VARIANTS)[number]["key"];

const BOX_VARIANT_KEYS: ReadonlySet<unknown> = new Set(BOX_VARIANTS.map((v) => v.key));

export function isBoxVariantKey(value: unknown): value is BoxVariantKey {
	return BOX_VARIANT_KEYS.has(value);
}

export type BoxAttributes = { variant?: BoxVariantKey; float?: FloatKey };

export const BOX_NODE_NAME = "box";

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		box: {
			/**
			 * Wrap the selected blocks in a box, or insert an empty one at an empty
			 * cursor. When the selection is already in a box, that box is changed
			 * instead: boxes never nest.
			 */
			setBox: (attributes?: BoxAttributes) => ReturnType;
			/** Change the variant and/or float of the box(es) around the selection. */
			updateBox: (attributes: BoxAttributes) => ReturnType;
			/** Take the content out of the box(es) around the selection. */
			unsetBox: () => ReturnType;
		};
	}
}

type FoundBox = { pos: number; node: ProseMirrorNode };

// The boxes the selection is inside of or covers (a node selection of a box counts).
export function boxesInSelection(state: EditorState): FoundBox[] {
	const { selection, doc } = state;
	const found = new Map<number, ProseMirrorNode>();
	for (let depth = selection.$from.depth; depth > 0; depth--) {
		const node = selection.$from.node(depth);
		if (node.type.name === BOX_NODE_NAME) {
			found.set(selection.$from.before(depth), node);
		}
	}
	doc.nodesBetween(selection.from, selection.to, (node, pos) => {
		if (node.type.name === BOX_NODE_NAME) found.set(pos, node);
	});
	return [...found].map(([pos, node]) => ({ pos, node })).sort((a, b) => a.pos - b.pos);
}

// Whether the attributes a command was given are all allowlisted keys.
function validAttributes(attributes: BoxAttributes): boolean {
	return (
		(attributes.variant === undefined || isBoxVariantKey(attributes.variant)) &&
		(attributes.float === undefined || isFloatKey(attributes.float))
	);
}

const nestedBoxKey = new PluginKey("boxNoNesting");

// A box block. Rendered with plain `renderHTML` (no node view) so the editor and the
// read-only content produce identical markup. Parsing reads `div[data-type="box"]`
// and its `data-variant` / `data-float` only, and only allowlisted keys, never
// inline styles: pasted HTML can't make a styled box by any other route.
export const Box = Node.create({
	name: BOX_NODE_NAME,
	group: "block",
	content: "block+",
	defining: true,

	addAttributes() {
		return {
			// A box with no `data-variant` is the default border; one with an unknown
			// variant keeps "" and so renders with no look at all.
			variant: {
				default: "border",
				parseHTML: (element: HTMLElement) => {
					const variant = element.getAttribute("data-variant");
					if (variant === null) return "border";
					return isBoxVariantKey(variant) ? variant : "";
				},
				renderHTML: (attributes: Record<string, unknown>) =>
					isBoxVariantKey(attributes["variant"])
						? { "data-variant": attributes["variant"] }
						: {},
			},
			float: floatAttribute,
		};
	},

	parseHTML() {
		return [{ tag: `div[data-type="${BOX_NODE_NAME}"]` }];
	},

	renderHTML({ HTMLAttributes }) {
		return ["div", mergeAttributes(HTMLAttributes, { "data-type": BOX_NODE_NAME }), 0];
	},

	addCommands() {
		return {
			setBox:
				(attributes = {}) =>
				({ state, commands }) => {
					if (!validAttributes(attributes)) return false;
					if (boxesInSelection(state).length > 0) {
						return Object.keys(attributes).length > 0
							? commands.updateBox(attributes)
							: true;
					}
					const attrs = {
						variant: attributes.variant ?? "border",
						float: attributes.float ?? "none",
					};
					if (state.selection.empty) {
						return commands.insertContent({
							type: this.name,
							attrs,
							content: [{ type: "paragraph" }],
						});
					}
					return commands.wrapIn(this.name, attrs);
				},

			updateBox:
				(attributes) =>
				({ state, tr, dispatch }) => {
					if (!validAttributes(attributes)) return false;
					const boxes = boxesInSelection(state);
					if (boxes.length === 0) return false;
					if (dispatch) {
						const changes: BoxAttributes = {};
						if (attributes.variant !== undefined) changes.variant = attributes.variant;
						if (attributes.float !== undefined) changes.float = attributes.float;
						for (const { pos, node } of boxes) {
							tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...changes });
						}
					}
					return true;
				},

			unsetBox:
				() =>
				({ state, tr, dispatch }) => {
					const boxes = boxesInSelection(state);
					if (boxes.length === 0) return false;
					if (dispatch) {
						// Back to front, so an unwrap doesn't shift the positions still to do.
						for (const { pos, node } of [...boxes].reverse()) {
							tr.replaceWith(pos, pos + node.nodeSize, node.content);
						}
					}
					return true;
				},
		};
	},

	// The commands never nest boxes, but pasted or inserted content can carry one
	// inside another; unwrap any such inner box so there is never a box in a box.
	addProseMirrorPlugins() {
		return [
			new Plugin({
				key: nestedBoxKey,
				appendTransaction: (transactions, _oldState, newState) => {
					if (!transactions.some((transaction) => transaction.docChanged)) return null;
					const nested: FoundBox[] = [];
					newState.doc.descendants((node, pos) => {
						if (node.type.name !== BOX_NODE_NAME) return;
						const $pos = newState.doc.resolve(pos);
						for (let depth = $pos.depth; depth > 0; depth--) {
							if ($pos.node(depth).type.name === BOX_NODE_NAME) {
								nested.push({ pos, node });
								return;
							}
						}
					});
					if (nested.length === 0) return null;
					const tr = newState.tr;
					for (const { pos, node } of nested.reverse()) {
						tr.replaceWith(pos, pos + node.nodeSize, Fragment.from(node.content));
					}
					return tr;
				},
			}),
		];
	},
});

export default Box;
