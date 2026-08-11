import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewContent,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import { type KeyboardEvent, useState } from "react";

export interface NoteOptions {
	HTMLAttributes: Record<string, unknown>;
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		note: {
			/**
			 * Wrap the current selection (or insert at the cursor) in a Note
			 * block visible only to the given usernames.
			 */
			setNote: (attributes?: { users?: string[] }) => ReturnType;
		};
	}
}

// Editable view: renders the target usernames as removable chips plus a text
// input to add more, rather than a raw comma-separated string field. This is
// the part worth stress-testing tiptap on — non-trivial attribute editing UI
// living inside the document, not just styled text.
function NoteView({ node, updateAttributes, deleteNode, editor }: NodeViewProps) {
	const [draft, setDraft] = useState("");
	const users = (node.attrs.users as string[]) ?? [];

	const addUser = (raw: string) => {
		const name = raw.trim();
		if (!name || users.includes(name)) return;
		updateAttributes({ users: [...users, name] });
	};

	const removeUser = (name: string) => {
		updateAttributes({ users: users.filter((user) => user !== name) });
	};

	const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
		if (event.key === "Enter" || event.key === ",") {
			event.preventDefault();
			addUser(draft);
			setDraft("");
		} else if (event.key === "Backspace" && draft === "" && users.length > 0) {
			removeUser(users[users.length - 1]);
		}
	};

	return (
		<NodeViewWrapper className="note-node" data-type="note">
			{editor.isEditable && (
				<button
					type="button"
					className="note-node-delete"
					aria-label="Delete note"
					contentEditable={false}
					onClick={deleteNode}
				>
					&times;
				</button>
			)}
			<div className="note-node-header" contentEditable={false}>
				<span className="note-node-label">Note for:</span>
				{users.map((user) => (
					<span key={user} className="note-node-chip">
						{user}
						{editor.isEditable && (
							<button
								type="button"
								className="note-node-chip-remove"
								aria-label={`Remove ${user}`}
								onClick={() => removeUser(user)}
							>
								&times;
							</button>
						)}
					</span>
				))}
				{editor.isEditable && (
					<input
						className="note-node-user-input"
						type="text"
						value={draft}
						placeholder="Add username..."
						onChange={(event) => setDraft(event.target.value)}
						onKeyDown={handleKeyDown}
						onBlur={() => {
							addUser(draft);
							setDraft("");
						}}
					/>
				)}
			</div>
			<NodeViewContent className="note-node-content" />
		</NodeViewWrapper>
	);
}

// A block node whose `users` attribute names who the note is targeted at.
// Equivalent to the old BBCode `[note="alice,bob"]...[/note]` block, but
// modeled as a typed node (attribute + child content) instead of a regex
// pair. Visibility enforcement (hiding the node's content from anyone not
// in `users`) is a backend concern and out of scope here.
export const Note = Node.create<NoteOptions>({
	name: "note",
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
			users: {
				default: [] as string[],
				parseHTML: (element) => {
					const raw = element.getAttribute("data-users") ?? "";
					return raw
						.split(",")
						.map((user) => user.trim())
						.filter(Boolean);
				},
				renderHTML: (attributes) => {
					const users = (attributes.users as string[]) ?? [];
					if (users.length === 0) return {};
					return { "data-users": users.join(",") };
				},
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: `div[data-type="${this.name}"]`,
				// The header (recipient chips) isn't editable document content,
				// so point parseHTML at the inner content wrapper instead of
				// letting it read every child element as block content.
				contentElement: ".note-node-content",
			},
		];
	},

	renderHTML({ node, HTMLAttributes }) {
		const users = (node.attrs.users as string[]) ?? [];
		const label = users.length > 0 ? `Note for: ${users.join(", ")}` : "Note";

		return [
			"div",
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
				"data-type": this.name,
			}),
			["div", { class: "note-node-header" }, label],
			["div", { class: "note-node-content" }, 0],
		];
	},

	addNodeView() {
		return ReactNodeViewRenderer(NoteView);
	},

	addCommands() {
		return {
			setNote:
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

export default Note;
