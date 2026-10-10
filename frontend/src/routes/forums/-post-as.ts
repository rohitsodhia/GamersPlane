import type { PostableCharacter } from "#/queries/forums";

export type CharacterType = PostableCharacter["type"];

// Who a post is written as: the user (`characterId` null), or a character with
// one of its avatars (`avatarId` null is the character's primary).
export type PostAsValue = { characterId: number | null; avatarId: number | null };

export const PLAYER: PostAsValue = { characterId: null, avatarId: null };

export const CHARACTER_TYPES: { type: CharacterType; label: string }[] = [
	{ type: "pc", label: "PC" },
	{ type: "npc", label: "NPC" },
];

// How many of a type's characters are pulled up front as "recently used".
export const RECENT_LIMIT = 5;
// A type's list gets a filter box once it has more characters than this.
export const FILTER_THRESHOLD = 8;

export function defaultPostAs(data: {
	default_id: number | null;
	default_avatar_id: number | null;
}): PostAsValue {
	return data.default_id === null
		? PLAYER
		: { characterId: data.default_id, avatarId: data.default_avatar_id };
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

// The list as shown: the most recently used characters first, then the rest in
// the order given. `recentCount` is how many lead the list, so the caller can
// put a divider after them (only when something follows). The filter narrows
// both parts.
export function orderCharacters(
	characters: PostableCharacter[],
	query = "",
): { items: PostableCharacter[]; recentCount: number } {
	const recent = characters
		.filter((character) => character.last_used_at !== null)
		.sort(
			(a, b) =>
				Date.parse(b.last_used_at as string) - Date.parse(a.last_used_at as string),
		)
		.slice(0, RECENT_LIMIT);
	const recentIds = new Set(recent.map((character) => character.id));
	const rest = characters.filter((character) => !recentIds.has(character.id));
	const shownRecent = recent.filter((character) => matchesQuery(character, query));
	const shownRest = rest.filter((character) => matchesQuery(character, query));
	return {
		items: [...shownRecent, ...shownRest],
		recentCount: shownRecent.length,
	};
}

export function showsFilter(characters: PostableCharacter[]): boolean {
	return characters.length > FILTER_THRESHOLD;
}

export function pickCharacter(character: PostableCharacter): PostAsValue {
	return { characterId: character.id, avatarId: null };
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
	if (value.characterId === null) return "player";
	return (
		characters.find((character) => character.id === value.characterId)?.type ?? null
	);
}

// Opening a type's list picks its first entry unless one of the type is already
// chosen. Null means leave the value as it is.
export function selectOnOpen(
	characters: PostableCharacter[],
	type: CharacterType,
	value: PostAsValue,
): PostAsValue | null {
	const ofType = charactersOfType(characters, type);
	if (ofType.some((character) => character.id === value.characterId)) return null;
	const [first] = orderCharacters(ofType).items;
	return first ? pickCharacter(first) : null;
}

// The `posted_as_id` / `posted_avatar_id` part of an edit request: only what
// moved off what the post had, so an unchanged or hidden picker never clears
// anything. `initial.avatarId` is the avatar the post showed (a resolved id), so
// both sides are resolved before comparing. Changing the character resets the
// avatar on the server, so an avatar is only sent with it when it isn't the
// primary.
export function changedPostedAs(
	initial: PostAsValue,
	current: PostAsValue,
	characters: PostableCharacter[],
): { posted_as_id?: number | null; posted_avatar_id?: number | null } {
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
