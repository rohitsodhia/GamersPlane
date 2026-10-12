import type { JSONContent } from "@tiptap/core";
import type { ContentNpc } from "#/queries/quick-npcs";

export const MAX_ROSTER_TITLE_LENGTH = 100;

// Replaces every speech block (at any depth) with its own content, led by a
// paragraph naming the speaker in bold ("**Name:**"), and every roster with a
// paragraph of its title in bold ("**Title:**") then its names, comma-separated
// (just the names with no title). For quoting a post: a quote is a reference, so it
// mustn't carry NPC ids the quoter may not be allowed to use.
export function flattenNpcBlocks(
	nodes: JSONContent[],
	npcs: readonly ContentNpc[],
): JSONContent[] {
	return nodes.flatMap((node): JSONContent[] => {
		if (node.type === "npcRoster") {
			return [rosterParagraph(node.attrs, speakerLookup(npcs))];
		}
		const children = node.content ? flattenNpcBlocks(node.content, npcs) : undefined;
		if (node.type !== "npcSpeaker") {
			return children ? [{ ...node, content: children }] : [node];
		}
		const name = speakerFor(node.attrs?.npcId, speakerLookup(npcs)).name;
		return [
			{
				type: "paragraph",
				content: [{ type: "text", text: `${name}:`, marks: [{ type: "bold" }] }],
			},
			...(children ?? []),
		];
	});
}

function rosterParagraph(
	attrs: JSONContent["attrs"],
	lookup: SpeakerLookup,
): JSONContent {
	const names = rosterIds(attrs?.npcIds)
		.map((id) => speakerFor(id, lookup).name)
		.join(", ");
	const title = typeof attrs?.title === "string" ? attrs.title.trim() : "";
	// Empty text nodes aren't allowed, so a missing part is left out.
	const content: JSONContent[] = [];
	if (title) {
		content.push({ type: "text", text: `${title}:`, marks: [{ type: "bold" }] });
	}
	if (names) content.push({ type: "text", text: title ? ` ${names}` : names });
	return content.length > 0 ? { type: "paragraph", content } : { type: "paragraph" };
}

// The well-formed ids of a roster's `npcIds` attr, in order.
export function rosterIds(value: unknown): number[] {
	return Array.isArray(value)
		? value.filter((id): id is number => Number.isInteger(id) && id > 0)
		: [];
}

const INITIAL_PATTERN = /\p{L}|\p{N}/u;

// The first letter or digit of a name, for an NPC with no image.
export function initialOf(name: string): string {
	return (
		Array.from(name).find((char) => INITIAL_PATTERN.test(char)) ?? "?"
	).toUpperCase();
}

// What a speaker block shows for its NPC: only the id is stored in the document.
export type SpeakerDisplay = {
	name: string;
	image: { url: string } | null;
};

export type SpeakerLookup = Record<number, SpeakerDisplay>;

export const UNKNOWN_SPEAKER: SpeakerDisplay = { name: "Unknown NPC", image: null };

// The NPCs as an id-keyed lookup for rendering saved posts.
export function speakerLookup(npcs: readonly ContentNpc[] = []): SpeakerLookup {
	return Object.fromEntries(npcs.map((npc) => [npc.id, npc]));
}

// What to show for a block's `npcId`: a missing or unlisted NPC (never saved with
// the post, or since lost) gets a neutral placeholder rather than failing.
export function speakerFor(npcId: unknown, lookup: SpeakerLookup): SpeakerDisplay {
	return typeof npcId === "number"
		? (lookup[npcId] ?? UNKNOWN_SPEAKER)
		: UNKNOWN_SPEAKER;
}

// The editor's view of a block's NPC: the live library list first, then the
// post's own `content_npcs` (which still has an NPC deleted since it was written).
export function findSpeaker(
	npcId: unknown,
	listed: readonly ContentNpc[],
	fallback: readonly ContentNpc[],
): SpeakerDisplay {
	return speakerFor(npcId, { ...speakerLookup(fallback), ...speakerLookup(listed) });
}

// The library's NPCs whose name contains the search text, keeping their order.
export function filterSpeakers<T extends { name: string }>(
	npcs: readonly T[],
	query: string,
): T[] {
	const needle = query.trim().toLocaleLowerCase();
	if (needle === "") return [...npcs];
	return npcs.filter((npc) => npc.name.toLocaleLowerCase().includes(needle));
}
