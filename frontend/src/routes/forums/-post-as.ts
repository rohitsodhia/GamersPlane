import type { PostableCharacter } from "#/queries/forums";

// The select's key for "post as yourself"; character ids are numeric strings.
export const PLAYER_KEY = "player";

export type PostAsOption = { key: string; label: string };

export function postAsKey(id: number | null): string {
	return id === null ? PLAYER_KEY : String(id);
}

export function postAsId(key: string): number | null {
	return key === PLAYER_KEY ? null : Number(key);
}

// "Player", then the characters. Another player's character shows its owner. A
// current character missing from the list (it left the game) is kept so the
// select still reflects the post.
export function postAsOptions(
	characters: PostableCharacter[],
	viewerId: number | undefined,
	current: { id: number; name: string } | null = null,
): PostAsOption[] {
	const options: PostAsOption[] = [{ key: PLAYER_KEY, label: "Player" }];
	for (const character of characters) {
		options.push({
			key: postAsKey(character.id),
			label:
				character.owner.id === viewerId
					? character.name
					: `${character.name} (${character.owner.username})`,
		});
	}
	if (current && !characters.some((character) => character.id === current.id)) {
		options.push({ key: postAsKey(current.id), label: current.name });
	}
	return options;
}

// The `posted_as_id` part of an edit request: only when the selection moved off
// what the post had, so an unchanged or hidden picker never clears anything.
export function changedPostedAs(
	initial: number | null,
	current: number | null,
): { posted_as_id?: number | null } {
	return current === initial ? {} : { posted_as_id: current };
}
