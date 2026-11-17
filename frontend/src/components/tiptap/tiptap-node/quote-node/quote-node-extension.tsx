import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewContent,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import clsx from "clsx";
import { closestNode } from "#/components/tiptap/tiptap-extension/closest-node";
import { NO_PASSWORD_MANAGER_ATTRS } from "#/lib/constants";

export interface QuoteOptions {
	HTMLAttributes: Record<string, unknown>;
}

// The quote block's two looks: a quote of someone (optionally named), and v1's
// out-of-character aside (`[ooc]`), which names nobody. The document stores the key
// only; anything but "ooc" reads as a plain quote.
export const QUOTE_VARIANTS = ["quote", "ooc"] as const;

export type QuoteVariant = (typeof QUOTE_VARIANTS)[number];

export function quoteVariant(value: unknown): QuoteVariant {
	return value === "ooc" ? "ooc" : "quote";
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		quote: {
			/**
			 * Wrap the current selection (or insert at the cursor) in a Quote
			 * block, optionally naming who is being quoted.
			 */
			setQuote: (attributes?: {
				quotee?: string;
				variant?: QuoteVariant;
			}) => ReturnType;
			/**
			 * Make the selection out-of-character: change the quote around it to an OOC
			 * block, or wrap it in a new one. Inside an OOC block already, take the
			 * content back out of it.
			 */
			toggleOoc: () => ReturnType;
		};
	}
}

function quoteeLabel(quotee: string) {
	return quotee ? `${quotee} says:` : "Quote:";
}

const OOC_LABEL = "OOC:";

// v1 rendered `[ooc]` as `<blockquote class="oocText"><div>OOC:</div>...`. Read the
// content from a copy without that label div.
function legacyOocContent(element: HTMLElement): HTMLElement {
	const clone = element.cloneNode(true) as HTMLElement;
	const first = clone.firstElementChild;
	if (first && first.tagName === "DIV") first.remove();
	return clone;
}

// Editable view: renders the quotee name as a single text field in the
// header, rather than the removable-chip list note-node-extension.tsx uses
// for its (multi-value) `users` attribute.
function QuoteView({ node, updateAttributes, deleteNode, editor }: NodeViewProps) {
	const quotee = (node.attrs.quotee as string) ?? "";
	const isOoc = quoteVariant(node.attrs.variant) === "ooc";

	return (
		<NodeViewWrapper
			className={clsx("quote-node", isOoc && "ooc")}
			data-type="quote"
			data-variant={isOoc ? "ooc" : undefined}
		>
			{editor.isEditable && (
				<button
					type="button"
					className="quote-node-delete"
					aria-label={isOoc ? "Delete OOC block" : "Delete quote"}
					contentEditable={false}
					onClick={deleteNode}
				>
					&times;
				</button>
			)}
			<div
				className={clsx("quote-node-header", isOoc ? "ooc-label" : "quotee")}
				contentEditable={false}
			>
				{isOoc ? (
					OOC_LABEL
				) : editor.isEditable ? (
					<>
						<input
							className="quote-node-quotee-input"
							type="text"
							name="quote_author"
							autoComplete="off"
							{...NO_PASSWORD_MANAGER_ATTRS}
							value={quotee}
							placeholder="Username"
							onChange={(event) => updateAttributes({ quotee: event.target.value })}
						/>
						<span className="quote-node-suffix">{quotee ? "says:" : "Quote:"}</span>
					</>
				) : (
					quoteeLabel(quotee)
				)}
			</div>
			<NodeViewContent className="quote-node-content" />
		</NodeViewWrapper>
	);
}

// A block node whose `quotee` attribute names who is being quoted.
// Equivalent to the BBCode `[quote="alice"]...[/quote]` block (see
// _tag_quote in api/src/app/helpers/bbcode.py), modeled the same way the
// Note extension models `[note]` — a typed node with an attribute plus
// child content, instead of a regex pair.
export const Quote = Node.create<QuoteOptions>({
	name: "quote",
	group: "block",
	content: "block+",
	defining: true,
	isolating: true,

	addOptions() {
		return {
			HTMLAttributes: {},
		};
	},

	addAttributes() {
		return {
			quotee: {
				default: "",
				parseHTML: (element) => element.getAttribute("data-quotee") ?? "",
				renderHTML: (attributes) => {
					const quotee = (attributes.quotee as string) ?? "";
					// An OOC block names nobody, so a stale quotee isn't written out.
					if (!quotee || quoteVariant(attributes.variant) === "ooc") return {};
					return { "data-quotee": quotee };
				},
			},
			// Anything but "ooc" (or v1's `oocText` class) is a plain quote.
			variant: {
				default: "quote",
				parseHTML: (element) =>
					element.getAttribute("data-variant") === "ooc" ||
					element.classList.contains("oocText")
						? "ooc"
						: "quote",
				renderHTML: (attributes) =>
					quoteVariant(attributes.variant) === "ooc" ? { "data-variant": "ooc" } : {},
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: `blockquote[data-type="${this.name}"]`,
				// Above the stock blockquote rule, which would otherwise win the tie.
				priority: 60,
				contentElement: ".quote-node-content",
			},
			// v1's `[ooc]`, as stored HTML.
			{
				tag: "blockquote.oocText, div.oocText",
				priority: 60,
				contentElement: legacyOocContent,
			},
		];
	},

	renderHTML({ node, HTMLAttributes }) {
		const quotee = (node.attrs.quotee as string) ?? "";
		const isOoc = quoteVariant(node.attrs.variant) === "ooc";

		return [
			"blockquote",
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
				class: isOoc ? "quote ooc" : "quote",
				"data-type": this.name,
			}),
			isOoc
				? ["div", { class: "ooc-label" }, OOC_LABEL]
				: ["div", { class: "quotee" }, quoteeLabel(quotee)],
			["div", { class: "quote-node-content" }, 0],
		];
	},

	addNodeView() {
		return ReactNodeViewRenderer(QuoteView);
	},

	addCommands() {
		return {
			setQuote:
				(attributes) =>
				({ commands, state }) => {
					if (state.selection.empty) {
						return commands.insertContent({
							type: this.name,
							attrs: attributes,
							content: [{ type: "paragraph" }],
						});
					}
					return commands.wrapIn(this.name, attributes);
				},

			toggleOoc:
				() =>
				({ state, tr, dispatch, commands }) => {
					const found = closestNode(state, this.name);
					if (!found) return commands.setQuote({ variant: "ooc" });
					if (dispatch) {
						if (quoteVariant(found.node.attrs.variant) === "ooc") {
							tr.replaceWith(
								found.pos,
								found.pos + found.node.nodeSize,
								found.node.content,
							);
						} else {
							tr.setNodeMarkup(found.pos, undefined, {
								...found.node.attrs,
								variant: "ooc",
								quotee: "",
							});
						}
					}
					return true;
				},
		};
	},
});

export default Quote;
