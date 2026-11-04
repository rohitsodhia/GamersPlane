import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewContent,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import clsx from "clsx";
import { createContext, useContext, useId } from "react";
import { Select } from "#/components/Select";
import type { SearchUser } from "#/queries/users";
import type { MentionLookup } from "../mention-node/mention";
import { MentionContext } from "../mention-node/mention-node-extension";
import {
	MAX_NOTE_RECIPIENTS,
	NOTE_MODES,
	type NoteMode,
	noteLabel,
	noteMode,
	noteRecipientName,
	noteStubText,
	noteUserIds,
} from "./note";
import { NoteRecipientPicker } from "./note-recipient-picker";

export interface NoteOptions {
	HTMLAttributes: Record<string, unknown>;
	// Read-only rendering (`generateHTML`): the names of the users the document's
	// notes name, by id (the post's `note_recipients`). The document only holds ids.
	recipients: MentionLookup;
	// Read-only rendering: the post author's name, for the stub a reader who can't
	// read a note sees ("<author> sent a note to ...").
	author: string | null;
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		note: {
			/**
			 * Wrap the current selection (or insert at the cursor) in a Note
			 * block for the users with the given ids.
			 */
			setNote: (attributes?: { userIds?: number[]; mode?: NoteMode }) => ReturnType;
		};
	}
}

// What the editable node view needs from the surrounding Editor besides the names
// (those come from `MentionContext`): a way to tell the Editor about a user just
// picked, so their name shows before the post is saved.
export const NoteContext = createContext<{ remember: (user: SearchUser) => void }>({
	remember: () => {},
});

const MODE_LABELS: Record<NoteMode, string> = {
	note: "Note",
	private: "Private",
};

const MODE_HINTS: Record<NoteMode, string> = {
	note: "Others see that a note was sent, not what it says.",
	private: "Hidden from everyone but its recipients, the GM, and moderators.",
};

// A stub the API sent in place of a note this viewer can't read.
function HiddenNoteView({ node }: NodeViewProps) {
	const names = useContext(MentionContext);
	const ids = noteUserIds(node.attrs["userIds"]);

	return (
		<NodeViewWrapper className="note-node note-node-hidden" contentEditable={false}>
			{noteStubText(
				null,
				ids.map((id) => noteRecipientName(id, names)),
			)}
		</NodeViewWrapper>
	);
}

// Editable view: the mode toggle and the recipients as removable chips, with a user
// search to add more. The document only keeps the ids.
function NoteView(props: NodeViewProps) {
	const { node, updateAttributes, deleteNode, editor } = props;
	const names = useContext(MentionContext);
	const { remember } = useContext(NoteContext);
	const modeId = useId();
	if (node.attrs["hidden"] === true) return <HiddenNoteView {...props} />;

	const mode = noteMode(node.attrs["mode"]);
	const userIds = noteUserIds(node.attrs["userIds"]);
	const editable = editor.isEditable;

	return (
		<NodeViewWrapper
			className={clsx("note-node", mode === "private" && "note-node-private")}
			data-type="note"
			data-mode={mode}
		>
			{editable && (
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
				{editable ? (
					<>
						<Select
							id={modeId}
							className="note-node-mode"
							ariaLabel="Note visibility"
							items={[...NOTE_MODES]}
							getId={(item) => item}
							getLabel={(item) => MODE_LABELS[item]}
							selectedId={mode}
							onChange={(value) => updateAttributes({ mode: noteMode(value) })}
						/>
						<span className="note-node-label">for:</span>
					</>
				) : (
					<span className="note-node-label">{noteLabel(mode, userIds.length > 0)}</span>
				)}
				{userIds.map((id) => (
					<span key={id} className="note-node-chip">
						{noteRecipientName(id, names)}
						{editable && (
							<button
								type="button"
								className="note-node-chip-remove"
								aria-label={`Remove ${noteRecipientName(id, names)}`}
								onClick={() =>
									updateAttributes({ userIds: userIds.filter((other) => other !== id) })
								}
							>
								&times;
							</button>
						)}
					</span>
				))}
				{editable && userIds.length < MAX_NOTE_RECIPIENTS && (
					<NoteRecipientPicker
						exclude={userIds}
						onPick={(user) => {
							remember(user);
							updateAttributes({ userIds: [...userIds, user.id] });
						}}
					/>
				)}
				{editable && <span className="note-node-hint">{MODE_HINTS[mode]}</span>}
			</div>
			<NodeViewContent className="note-node-content" />
		</NodeViewWrapper>
	);
}

// A block node whose `userIds` attribute names who the note is for, and whose `mode`
// says what everyone else sees: a "note" leaves a stub saying it exists, a
// "private" one leaves nothing. Equivalent to the old BBCode `[note]` and
// `[private]` blocks. Hiding is done by the API, which strips the text of any note
// the viewer can't read before it sends the post (`hidden: true` marks the stub it
// leaves); the frontend only draws what it is sent.
export const Note = Node.create<NoteOptions>({
	name: "note",
	group: "block",
	content: "block+",
	defining: true,
	isolating: true,

	addOptions() {
		return {
			HTMLAttributes: {},
			recipients: {},
			author: null,
		};
	},

	addAttributes() {
		return {
			userIds: {
				default: [] as number[],
				parseHTML: (element) =>
					noteUserIds(
						(element.getAttribute("data-user-ids") ?? "")
							.split(",")
							.map((id) => Number(id.trim())),
					),
				renderHTML: (attributes) => {
					const ids = noteUserIds(attributes["userIds"]);
					return ids.length > 0 ? { "data-user-ids": ids.join(",") } : {};
				},
			},
			mode: {
				default: "note",
				parseHTML: (element) => noteMode(element.getAttribute("data-mode")),
				renderHTML: (attributes) => ({ "data-mode": noteMode(attributes["mode"]) }),
			},
			// Set by the API on a note's stub only; never read back from pasted HTML
			// (the API refuses to save one).
			hidden: {
				default: false,
				parseHTML: () => false,
				rendered: false,
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
		const mode = noteMode(node.attrs["mode"]);
		const ids = noteUserIds(node.attrs["userIds"]);
		const names = ids.map((id) => noteRecipientName(id, this.options.recipients));

		if (node.attrs["hidden"] === true) {
			// No data-type, so a copy of the stub can't parse back into a note.
			return [
				"div",
				{ class: "note-node note-node-hidden" },
				noteStubText(this.options.author, names),
			];
		}

		return [
			"div",
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
				"data-type": this.name,
				class: clsx("note-node", mode === "private" && "note-node-private"),
			}),
			[
				"div",
				{ class: "note-node-header" },
				["span", { class: "note-node-label" }, noteLabel(mode, ids.length > 0)],
				...names.map((name): [string, Record<string, string>, string] => [
					"span",
					{ class: "note-node-chip" },
					name,
				]),
			],
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
