import { type JSONContent, mergeAttributes, Node } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { Plugin } from "@tiptap/pm/state";

export const POLL_NODE_NAME = "poll";

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		poll: {
			/**
			 * Insert the marker for where the thread's poll appears. Returns false (and
			 * inserts nothing) when the document already has one.
			 */
			insertPoll: () => ReturnType;
		};
	}
}

/** Positions of every poll node in the document, in order. */
function pollPositions(doc: ProseMirrorNode): number[] {
	const positions: number[] = [];
	doc.descendants((node, pos) => {
		if (node.type.name === POLL_NODE_NAME) positions.push(pos);
		return true;
	});
	return positions;
}

export function hasPoll(doc: ProseMirrorNode): boolean {
	return pollPositions(doc).length > 0;
}

/** Whether a document's JSON holds a poll marker anywhere. */
export function contentHasPoll(content: JSONContent | null | undefined): boolean {
	if (!content) return false;
	if (content.type === POLL_NODE_NAME) return true;
	return (content.content ?? []).some(contentHasPoll);
}

// Marks where the thread's poll appears inside the thread's first post. It carries
// no data: the poll itself lives on the thread, and this only says "put it here".
// An atom block with no attributes, rendered as an empty slot; the editor labels the
// slot with CSS (poll-node.scss), and the thread page fills it (see TiptapContent).
// A document holds at most one: the insert command refuses a second, and a paste or
// drop that brings extras has them removed again.
export const Poll = Node.create({
	name: POLL_NODE_NAME,
	group: "block",
	atom: true,
	selectable: true,
	draggable: true,

	parseHTML() {
		return [{ tag: `div[data-type="${POLL_NODE_NAME}"]` }];
	},

	renderHTML({ HTMLAttributes }) {
		return [
			"div",
			mergeAttributes(HTMLAttributes, {
				"data-type": POLL_NODE_NAME,
				class: "poll-slot",
			}),
		];
	},

	addCommands() {
		return {
			insertPoll:
				() =>
				({ state, commands }) => {
					if (hasPoll(state.doc)) return false;
					return commands.insertContent({ type: this.name });
				},
		};
	},

	addProseMirrorPlugins() {
		return [
			new Plugin({
				appendTransaction: (transactions, _oldState, newState) => {
					if (!transactions.some((tr) => tr.docChanged)) return null;
					const [, ...extras] = pollPositions(newState.doc);
					if (extras.length === 0) return null;
					const tr = newState.tr;
					// From the end, so earlier positions stay valid.
					for (const pos of extras.reverse()) {
						tr.delete(pos, pos + 1);
					}
					return tr;
				},
			}),
		];
	},
});

export default Poll;
