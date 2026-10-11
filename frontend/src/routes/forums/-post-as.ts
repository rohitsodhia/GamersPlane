import type { PostableCharacter } from "#/queries/forums";
import type { GameImage, GameNpc } from "#/queries/game";
import type { PostedNpcInput } from "#/queries/posts";

export type CharacterType = PostableCharacter["type"];

// A quick NPC to post as: a name and an optional library image. `id` is set when
// it's an existing name + image pair, null for one the server will find or make
// when the post is saved.
export type QuickNpcValue = {
	id: number | null;
	name: string;
	imageId: number | null;
};

// Who a post is written as: the user (`characterId` null), a character with one
// of its avatars (`avatarId` null is the character's primary), or a quick NPC.
export type PostAsValue =
	| { characterId: number | null; avatarId: number | null; npc?: undefined }
	| { characterId: null; avatarId: null; npc: QuickNpcValue };

export const PLAYER: PostAsValue = { characterId: null, avatarId: null };

export const CHARACTER_TYPES: { type: CharacterType; label: string }[] = [
	{ type: "pc", label: "PC" },
	{ type: "npc", label: "NPC" },
];

// How many of a type's characters are pulled up front as "recently used".
export const RECENT_LIMIT = 5;
// A type's list gets a filter box once it has more characters than this.
export const FILTER_THRESHOLD = 8;

export function npcValue(npc: GameNpc): PostAsValue {
	return {
		characterId: null,
		avatarId: null,
		npc: { id: npc.id, name: npc.name, imageId: npc.image?.id ?? null },
	};
}

export function defaultPostAs(data: {
	default_id: number | null;
	default_avatar_id: number | null;
	default_npc_id?: number | null;
	npcs?: GameNpc[];
}): PostAsValue {
	const npc = data.npcs?.find((n) => n.id === data.default_npc_id);
	if (npc) return npcValue(npc);
	return data.default_id === null
		? PLAYER
		: { characterId: data.default_id, avatarId: data.default_avatar_id };
}

// What an existing post is written as. A post only knows its NPC's image by URL,
// so the image id is left unknown; changedPostedAs tells the NPC by id.
export function postAsOfPost(post: {
	posted_as: { id: number; avatar_id: number | null } | null;
	posted_npc: { id: number; name: string } | null;
}): PostAsValue {
	if (post.posted_npc) {
		const { id, name } = post.posted_npc;
		return { characterId: null, avatarId: null, npc: { id, name, imageId: null } };
	}
	return post.posted_as
		? { characterId: post.posted_as.id, avatarId: post.posted_as.avatar_id }
		: PLAYER;
}

export function charactersOfType(
	characters: PostableCharacter[],
	type: CharacterType,
): PostableCharacter[] {
	return characters.filter((character) => character.type === type);
}

function matchesQuery(character: PostableCharacter, query: string): boolean {
	const needle = query.trim().toLowerCase();
	return (
		needle === "" ||
		character.name.toLowerCase().includes(needle) ||
		character.owner.username.toLowerCase().includes(needle)
	);
}

// The most recently used first (newest first, at most RECENT_LIMIT), then the
// rest in the order given. `recentCount` is how many lead the list, so the caller
// can put a divider after them. The filter narrows both parts.
function orderRecent<T>(
	items: T[],
	idOf: (item: T) => string | number,
	lastUsedOf: (item: T) => string | null,
	matches: (item: T) => boolean,
): { items: T[]; recentCount: number } {
	const recent = items
		.filter((item) => lastUsedOf(item) !== null)
		.sort(
			(a, b) =>
				Date.parse(lastUsedOf(b) as string) - Date.parse(lastUsedOf(a) as string),
		)
		.slice(0, RECENT_LIMIT);
	const recentIds = new Set(recent.map(idOf));
	const rest = items.filter((item) => !recentIds.has(idOf(item)));
	const shownRecent = recent.filter(matches);
	return {
		items: [...shownRecent, ...rest.filter(matches)],
		recentCount: shownRecent.length,
	};
}

// A row of the NPC list: an NPC character, a quick NPC, or the "create a quick
// NPC named ..." row.
export type NpcEntry =
	| { kind: "character"; key: string; character: PostableCharacter }
	| { kind: "npc"; key: string; npc: GameNpc }
	| { kind: "new"; key: string; name: string };

// The rows of a type's list: its characters, and for NPC the quick NPCs too.
export function entriesOfType(
	characters: PostableCharacter[],
	npcs: GameNpc[],
	type: CharacterType,
): NpcEntry[] {
	return [
		...charactersOfType(characters, type).map(
			(character): NpcEntry => ({
				kind: "character",
				key: `c${character.id}`,
				character,
			}),
		),
		...(type === "npc"
			? npcs.map((npc): NpcEntry => ({ kind: "npc", key: `n${npc.id}`, npc }))
			: []),
	];
}

function entryLastUsed(entry: NpcEntry): string | null {
	if (entry.kind === "character") return entry.character.last_used_at;
	return entry.kind === "npc" ? entry.npc.last_used_at : null;
}

function entryMatches(entry: NpcEntry, query: string): boolean {
	if (entry.kind === "character") return matchesQuery(entry.character, query);
	if (entry.kind === "new") return true;
	const needle = query.trim().toLowerCase();
	return needle === "" || entry.npc.name.toLowerCase().includes(needle);
}

// A type's list as shown: the most recently used entries first (characters and
// quick NPCs ranked together by when each was last used), then the rest in the
// order given.
export function orderEntries(
	entries: NpcEntry[],
	query = "",
): { items: NpcEntry[]; recentCount: number } {
	return orderRecent(
		entries,
		(entry) => entry.key,
		entryLastUsed,
		(entry) => entryMatches(entry, query),
	);
}

// The "New quick NPC: <name>" row for what was typed, unless a quick NPC already
// has exactly that name. With nothing typed, an unsaved NPC already chosen keeps
// its row so it stays visible in the list.
export function newNpcEntry(
	query: string,
	npcs: GameNpc[],
	value: PostAsValue,
): NpcEntry | null {
	const typed = query.trim();
	const name = typed || (value.npc && value.npc.id === null ? value.npc.name : "");
	if (name === "" || npcs.some((npc) => npc.name === name)) return null;
	return { kind: "new", key: "new", name };
}

export function showsFilter(entries: unknown[], canCreateNpc = false): boolean {
	return canCreateNpc || entries.length > FILTER_THRESHOLD;
}

// Which type buttons show: PC / NPC only when there is someone of the type to
// pick, except that a GM can always open NPC to make a quick NPC.
export function visibleTypes(
	characters: PostableCharacter[],
	npcs: GameNpc[],
	canCreateNpc: boolean,
): { type: CharacterType; label: string }[] {
	return CHARACTER_TYPES.filter(({ type }) =>
		type === "npc"
			? canCreateNpc || npcs.length > 0 || charactersOfType(characters, type).length > 0
			: charactersOfType(characters, type).length > 0,
	);
}

export function pickCharacter(character: PostableCharacter): PostAsValue {
	return { characterId: character.id, avatarId: null };
}

export function pickEntry(entry: NpcEntry): PostAsValue {
	if (entry.kind === "character") return pickCharacter(entry.character);
	if (entry.kind === "npc") return npcValue(entry.npc);
	return {
		characterId: null,
		avatarId: null,
		npc: { id: null, name: entry.name, imageId: null },
	};
}

export function isEntrySelected(entry: NpcEntry, value: PostAsValue): boolean {
	if (entry.kind === "character") {
		return !value.npc && value.characterId === entry.character.id;
	}
	if (!value.npc) return false;
	if (entry.kind === "npc") return value.npc.id === entry.npc.id;
	return value.npc.id === null && value.npc.name === entry.name;
}

// Matches the value to the list: an existing pair's image comes from it, so a
// value built before the list loaded (a post being edited) still shows it, and a
// new pair the server has since made takes its id.
export function resolveNpc(npc: QuickNpcValue, npcs: GameNpc[]): QuickNpcValue {
	const listed =
		npc.id === null
			? npcs.find((n) => n.name === npc.name && (n.image?.id ?? null) === npc.imageId)
			: npcs.find((n) => n.id === npc.id);
	return listed
		? { id: listed.id, name: npc.name, imageId: listed.image?.id ?? null }
		: npc;
}

// The URL of a quick NPC's image, found in the library, the NPC list or the
// post's own NPC.
export function npcImageUrl(
	npc: QuickNpcValue,
	images: GameImage[],
	npcs: GameNpc[],
	current: { id: number; image: string | null } | null = null,
): string | null {
	if (npc.imageId === null) return null;
	return (
		images.find((image) => image.id === npc.imageId)?.url ??
		npcs.find((n) => n.image?.id === npc.imageId)?.image?.url ??
		(current && current.id === npc.id ? current.image : null)
	);
}

// Choosing a thumbnail also chooses its character; the primary is stored as null.
export function pickAvatar(
	character: PostableCharacter,
	avatarId: number,
): PostAsValue {
	const avatar = character.avatars.find((a) => a.id === avatarId);
	return { characterId: character.id, avatarId: avatar?.is_primary ? null : avatarId };
}

// The id of the avatar `value` shows for `character`: the chosen one if it's
// still theirs, else the primary (null with no avatars).
export function effectiveAvatarId(
	character: PostableCharacter | undefined,
	avatarId: number | null,
): number | null {
	if (!character) return avatarId;
	if (avatarId !== null && character.avatars.some((a) => a.id === avatarId)) {
		return avatarId;
	}
	return character.avatars.find((a) => a.is_primary)?.id ?? null;
}

// Which of the Player / PC / NPC buttons is lit: null when the value is a
// character that isn't listed (a post's character that has since left the game).
export function modeOf(
	value: PostAsValue,
	characters: PostableCharacter[],
): "player" | CharacterType | null {
	if (value.npc) return "npc";
	if (value.characterId === null) return "player";
	return (
		characters.find((character) => character.id === value.characterId)?.type ?? null
	);
}

// Opening a type's list picks its first entry unless one of the type is already
// chosen. Null means leave the value as it is (also when the NPC list has nothing
// to pick yet, so a GM can type a new name).
export function selectOnOpen(
	characters: PostableCharacter[],
	type: CharacterType,
	value: PostAsValue,
	npcs: GameNpc[] = [],
): PostAsValue | null {
	const entries = entriesOfType(characters, npcs, type);
	if (value.npc ? type === "npc" : entries.some((e) => isEntrySelected(e, value))) {
		return null;
	}
	const [first] = orderEntries(entries).items;
	return first ? pickEntry(first) : null;
}

// The poster fields of a new post or thread.
export function postAsPayload(value: PostAsValue): {
	posted_as_id?: number | null;
	posted_avatar_id?: number | null;
	posted_npc?: PostedNpcInput;
} {
	if (value.npc) {
		return { posted_npc: { name: value.npc.name, image_id: value.npc.imageId } };
	}
	return { posted_as_id: value.characterId, posted_avatar_id: value.avatarId };
}

// Whether two quick NPC values are the same pair. An existing pair is told by its
// id (a post's NPC value doesn't know its image id), a new one by name and image.
function sameNpc(a: QuickNpcValue, b: QuickNpcValue): boolean {
	if (a.id !== null && b.id !== null) return a.id === b.id;
	return a.name === b.name && a.imageId === b.imageId;
}

// The `posted_as_id` / `posted_avatar_id` / `posted_npc` part of an edit
// request: only what moved off what the post had, so an unchanged or hidden
// picker never clears anything. `initial.avatarId` is the avatar the post showed
// (a resolved id), so both sides are resolved before comparing. Changing the
// character resets the avatar on the server, so an avatar is only sent with it
// when it isn't the primary. A quick NPC replaces the character on the server, but
// moving off an NPC must say so with `posted_npc: null`.
export function changedPostedAs(
	initial: PostAsValue,
	current: PostAsValue,
	characters: PostableCharacter[],
): {
	posted_as_id?: number | null;
	posted_avatar_id?: number | null;
	posted_npc?: PostedNpcInput | null;
} {
	if (current.npc) {
		if (initial.npc && sameNpc(initial.npc, current.npc)) return {};
		return { posted_npc: { name: current.npc.name, image_id: current.npc.imageId } };
	}
	if (initial.npc) {
		// Compared against the user: a character or the user replaces the NPC.
		return { posted_npc: null, ...changedPostedAs(PLAYER, current, characters) };
	}
	if (current.characterId !== initial.characterId) {
		return current.characterId === null || current.avatarId === null
			? { posted_as_id: current.characterId }
			: { posted_as_id: current.characterId, posted_avatar_id: current.avatarId };
	}
	if (current.characterId === null) return {};
	const character = characters.find((c) => c.id === current.characterId);
	return effectiveAvatarId(character, current.avatarId) ===
		effectiveAvatarId(character, initial.avatarId)
		? {}
		: { posted_avatar_id: current.avatarId };
}
