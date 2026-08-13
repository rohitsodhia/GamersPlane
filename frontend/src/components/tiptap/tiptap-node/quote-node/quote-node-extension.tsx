import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewContent,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";

export interface QuoteOptions {
	HTMLAttributes: Record<string, unknown>;
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		quote: {
			/**
			 * Wrap the current selection (or insert at the cursor) in a Quote
			 * block, optionally naming who is being quoted.
			 */
			setQuote: (attributes?: { quotee?: string }) => ReturnType;
		};
	}
}

function quoteeLabel(quotee: string) {
	return quotee ? `${quotee} says:` : "Quote:";
}

// Editable view: renders the quotee name as a single text field in the
// header, rather than the removable-chip list note-node-extension.tsx uses
// for its (multi-value) `users` attribute.
function QuoteView({ node, updateAttributes, deleteNode, editor }: NodeViewProps) {
	const quotee = (node.attrs.quotee as string) ?? "";

	return (
		<NodeViewWrapper className="quote-node" data-type="quote">
			{editor.isEditable && (
				<button
					type="button"
					className="quote-node-delete"
					aria-label="Delete quote"
					contentEditable={false}
					onClick={deleteNode}
				>
					&times;
				</button>
			)}
			<div className="quote-node-header quotee" contentEditable={false}>
				{editor.isEditable ? (
					<>
						<input
							className="quote-node-quotee-input"
							type="text"
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
					if (!quotee) return {};
					return { "data-quotee": quotee };
				},
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: `blockquote[data-type="${this.name}"]`,
				contentElement: ".quote-node-content",
			},
		];
	},

	renderHTML({ node, HTMLAttributes }) {
		const quotee = (node.attrs.quotee as string) ?? "";

		return [
			"blockquote",
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
				class: "quote",
				"data-type": this.name,
			}),
			["div", { class: "quotee" }, quoteeLabel(quotee)],
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
		};
	},
});

export default Quote;
