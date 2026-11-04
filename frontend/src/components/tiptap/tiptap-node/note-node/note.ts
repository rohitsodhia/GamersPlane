import type { JSONContent } from "@tiptap/core";
import {
	DELETED_MENTION_NAME,
	type MentionLookup,
} from "#/components/tiptap/tiptap-node/mention-node/mention";

// A note holds only its recipients' user ids; their names come from the post's
// `note_recipients`, like a mention's from `content_mentions`. The API strips the
// text of notes the viewer can't read: a "note" they can't read arrives as a
// `hidden` stub (no text, recipients kept), a "private" one doesn't arrive at all.

export type NoteMode = "note" | "private";

export const NOTE_MODES: readonly NoteMode[] = ["note", "private"];

// Most recipients one note may name (the API rejects more).
export const MAX_NOTE_RECIPIENTS = 20;

export function noteMode(mode: unknown): NoteMode {
	return mode === "private" ? "private" : "note";
}

// The well-formed ids of a note's `userIds` attr, once each. A missing or
// malformed attr (a note saved before ids existed) reads as no recipients.
export function noteUserIds(userIds: unknown): number[] {
	if (!Array.isArray(userIds)) return [];
	const ids = userIds.filter(
		(id): id is number => typeof id === "number" && Number.isInteger(id) && id > 0,
	);
	return [...new Set(ids)];
}

export function noteRecipientName(userId: number, lookup: MentionLookup): string {
	return lookup[userId] ?? DELETED_MENTION_NAME;
}

// "Note for:" / "Private note for:", or just "Note" / "Private note" with nobody
// named. The label ends in a colon exactly when names follow.
export function noteLabel(mode: NoteMode, hasRecipients: boolean): string {
	const base = mode === "private" ? "Private note" : "Note";
	return hasRecipients ? `${base} for:` : base;
}

// What a reader who can't read the note sees in its place.
export function noteStubText(author: string | null, names: readonly string[]): string {
	const who = author ?? "Someone";
	if (names.length === 0) return `${who}'s note`;
	return `${who} sent a note to ${names.join(", ")}`;
}

type NoteViewer = {
	userId: number | null;
	// A moderator of the forum or a GM of the game: reads every note.
	seesAllNotes: boolean;
};

function isNote(node: JSONContent): boolean {
	return node.type === "note";
}

function canKeepNote(node: JSONContent, viewer: NoteViewer): boolean {
	// A stub holds no text; it must never be quoted, whoever is quoting.
	if (node.attrs?.["hidden"] === true) return false;
	if (viewer.seesAllNotes) return true;
	return (
		viewer.userId !== null &&
		noteUserIds(node.attrs?.["userIds"]).includes(viewer.userId)
	);
}

// The nodes with every note the viewer isn't a recipient of (and doesn't see all
// notes) removed, anywhere in the tree. A quote repeats the post to everyone who
// reads the reply, so it may only carry notes its quoter was meant to read. A
// container left with nothing keeps an empty paragraph, as it needs a block.
export function dropUnreadableNotes(
	nodes: readonly JSONContent[],
	viewer: NoteViewer,
): JSONContent[] {
	const kept: JSONContent[] = [];
	for (const node of nodes) {
		if (isNote(node) && !canKeepNote(node, viewer)) continue;
		if (!node.content || node.content.length === 0) {
			kept.push(node);
			continue;
		}
		const content = dropUnreadableNotes(node.content, viewer);
		kept.push({
			...node,
			content: content.length > 0 ? content : [{ type: "paragraph" }],
		});
	}
	return kept;
}
