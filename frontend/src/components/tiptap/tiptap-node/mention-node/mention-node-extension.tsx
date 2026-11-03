import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import { Suggestion, type SuggestionOptions } from "@tiptap/suggestion";
import clsx from "clsx";
import { createContext, useContext } from "react";
import { type MentionLookup, mentionHref, mentionLabel, mentionName } from "./mention";

export interface MentionOptions {
	HTMLAttributes: Record<string, unknown>;
	// Read-only rendering (`generateHTML`): the users the document's mentions name,
	// by id. The document itself only ever holds the id.
	users: MentionLookup;
	// The editable editor's `@` picker; leave unset for read-only rendering.
	suggestion?: Omit<SuggestionOptions, "editor">;
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		mention: {
			/** Insert a mention of the user with this id at the cursor. */
			insertMention: (attributes: { userId: number }) => ReturnType;
		};
	}
}

// What the editable node view needs from the surrounding Editor: the usernames of
// the edited post's `content_mentions` plus anyone picked since.
export const MentionContext = createContext<MentionLookup>({});

function MentionView({ node }: NodeViewProps) {
	const users = useContext(MentionContext);
	const userId: unknown = node.attrs.userId;

	return (
		// A plain span, not a link: a click in the editor selects the chip.
		<NodeViewWrapper
			as="span"
			className={clsx(
				"mention",
				mentionName(userId, users) === null && "mention-deleted",
			)}
			data-type="mention"
		>
			{mentionLabel(userId, users)}
		</NodeViewWrapper>
	);
}

// An inline @username chip. Only the user's id is stored: the name is looked up
// when the post is shown, so a renamed user's old mentions follow the rename (and
// a deleted user still renders, as "@[deleted]").
export const Mention = Node.create<MentionOptions>({
	name: "mention",
	group: "inline",
	inline: true,
	atom: true,
	selectable: true,

	addOptions() {
		return {
			HTMLAttributes: {},
			users: {},
		};
	},

	addAttributes() {
		return {
			userId: {
				default: null,
				parseHTML: (element) => {
					const id = Number(element.getAttribute("data-user-id"));
					return Number.isInteger(id) && id > 0 ? id : null;
				},
				renderHTML: (attributes) =>
					typeof attributes.userId === "number"
						? { "data-user-id": String(attributes.userId) }
						: {},
			},
		};
	},

	parseHTML() {
		return [{ tag: '[data-type="mention"]', priority: 60 }];
	},

	renderHTML({ node, HTMLAttributes }) {
		const userId: unknown = node.attrs.userId;
		const href = mentionHref(userId, this.options.users);
		const attributes = mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
			"data-type": this.name,
			class: href === null ? "mention mention-deleted" : "mention",
		});

		return href === null
			? ["span", attributes, mentionLabel(userId, this.options.users)]
			: ["a", { ...attributes, href }, mentionLabel(userId, this.options.users)];
	},

	addProseMirrorPlugins() {
		const { suggestion } = this.options;
		return suggestion ? [Suggestion({ editor: this.editor, ...suggestion })] : [];
	},

	addNodeView() {
		return ReactNodeViewRenderer(MentionView, { as: "span" });
	},

	addCommands() {
		return {
			insertMention:
				(attributes) =>
				({ commands }) =>
					commands.insertContent([
						{ type: this.name, attrs: attributes },
						// A space after, so typing carries on outside the chip.
						{ type: "text", text: " " },
					]),
		};
	},
});

export default Mention;
