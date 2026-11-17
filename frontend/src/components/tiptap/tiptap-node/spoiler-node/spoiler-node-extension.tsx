import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewContent,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import { closestNode } from "#/components/tiptap/tiptap-extension/closest-node";

export const SPOILER_NODE_NAME = "spoiler";
export const DEFAULT_SPOILER_TITLE = "Spoiler";
export const MAX_SPOILER_TITLE_LENGTH = 100;

/** A spoiler's title as it renders: trimmed and capped, or the default when empty. */
export function spoilerTitle(value: unknown): string {
	if (typeof value !== "string") return DEFAULT_SPOILER_TITLE;
	const title = value.trim().slice(0, MAX_SPOILER_TITLE_LENGTH).trim();
	return title || DEFAULT_SPOILER_TITLE;
}

// v1 rendered `[spoiler=Title]` (and `[snippet]`, a spoiler with a copy helper) as
// `<blockquote class="spoiler closed"><div class="tag">[ <span>+</span><span>-</span> ]
// Title</div><div class="hidden">...</div></blockquote>`. A GM-sheet `charsheet`
// spoiler is not a spoiler here.
function isLegacySpoiler(element: HTMLElement): boolean {
	return (
		element.classList.contains("spoiler") && !element.classList.contains("charsheet")
	);
}

function legacyTitle(element: HTMLElement): string {
	const tag = element.querySelector(":scope > .tag");
	return (tag?.textContent ?? "").replace(/^\[[\s+-]*\]\s*/, "");
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		spoiler: {
			/** Wrap the selected blocks in a spoiler, or insert an empty one at the cursor. */
			setSpoiler: (attributes?: { title?: string }) => ReturnType;
			/** Take the content out of the spoiler the caret is in. */
			unsetSpoiler: () => ReturnType;
			/** Unwrap the spoiler the caret is in, or wrap the selection in a new one. */
			toggleSpoiler: () => ReturnType;
		};
	}
}

// Editing view: always open, with the title as a text field. Reading uses the plain
// `<details>` from `renderHTML` below (the read-only content never mounts node views),
// which starts collapsed.
function SpoilerView({ node, updateAttributes, deleteNode, editor }: NodeViewProps) {
	const title = typeof node.attrs.title === "string" ? node.attrs.title : "";

	return (
		<NodeViewWrapper className="spoiler-node" data-type={SPOILER_NODE_NAME}>
			<div className="spoiler-node-header" contentEditable={false}>
				{editor.isEditable ? (
					<>
						<input
							className="spoiler-node-title-input"
							type="text"
							name="spoiler_title"
							aria-label="Spoiler title"
							maxLength={MAX_SPOILER_TITLE_LENGTH}
							value={title}
							placeholder={DEFAULT_SPOILER_TITLE}
							onChange={(event) => updateAttributes({ title: event.target.value })}
						/>
						<button
							type="button"
							className="spoiler-node-delete"
							aria-label="Delete spoiler"
							onClick={deleteNode}
						>
							&times;
						</button>
					</>
				) : (
					spoilerTitle(title)
				)}
			</div>
			<NodeViewContent className="spoiler-node-content" />
		</NodeViewWrapper>
	);
}

// A collapsible block with a title: v1's `[spoiler]`, with `[snippet]` folded in.
// Rendered as `<details>`/`<summary>` so it works with no script in the read-only
// content. The title is a plain text attribute, capped and trimmed on both read and
// write; the parse rules read `data-title` (or v1's tag text) and nothing else.
export const Spoiler = Node.create({
	name: SPOILER_NODE_NAME,
	group: "block",
	content: "block+",
	defining: true,

	addAttributes() {
		return {
			title: {
				default: DEFAULT_SPOILER_TITLE,
				parseHTML: (element: HTMLElement) =>
					spoilerTitle(
						isLegacySpoiler(element)
							? legacyTitle(element)
							: element.getAttribute("data-title"),
					),
				renderHTML: (attributes: Record<string, unknown>) => ({
					"data-title": spoilerTitle(attributes["title"]),
				}),
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: `details[data-type="${SPOILER_NODE_NAME}"]`,
				contentElement: ".spoiler-content",
			},
			// v1's markup. Above the stock blockquote rule so a spoiler isn't read as a quote.
			{
				tag: "blockquote.spoiler, div.spoiler",
				priority: 60,
				getAttrs: (element) => (isLegacySpoiler(element) ? null : false),
				contentElement: ":scope > .hidden",
			},
		];
	},

	renderHTML({ node, HTMLAttributes }) {
		return [
			"details",
			mergeAttributes(HTMLAttributes, { "data-type": SPOILER_NODE_NAME }),
			["summary", {}, spoilerTitle(node.attrs["title"])],
			["div", { class: "spoiler-content" }, 0],
		];
	},

	addNodeView() {
		return ReactNodeViewRenderer(SpoilerView);
	},

	addCommands() {
		return {
			setSpoiler:
				(attributes = {}) =>
				({ state, commands }) => {
					const attrs = {
						title:
							attributes.title === undefined ? DEFAULT_SPOILER_TITLE : attributes.title,
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

			unsetSpoiler:
				() =>
				({ state, tr, dispatch }) => {
					const found = closestNode(state, this.name);
					if (!found) return false;
					if (dispatch) {
						tr.replaceWith(
							found.pos,
							found.pos + found.node.nodeSize,
							found.node.content,
						);
					}
					return true;
				},

			toggleSpoiler:
				() =>
				({ state, commands }) =>
					closestNode(state, this.name)
						? commands.unsetSpoiler()
						: commands.setSpoiler(),
		};
	},
});

export default Spoiler;
