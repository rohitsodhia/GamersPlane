import type { GameDetails, GamePlayer, GamePlayerCharacter } from "#/queries/game";

export type CharacterGroup = {
	player: Pick<GamePlayer, "id" | "username">;
	isViewer: boolean;
	characters: GamePlayerCharacter[];
};

/**
 * The game's approved characters, grouped by their (accepted) player. The
 * viewer's own group comes first; the rest keep the API's order. Players with
 * nothing approved are left out.
 */
export function approvedCharacterGroups(
	players: GamePlayer[],
	viewerId: number | null,
): CharacterGroup[] {
	const groups = players
		.filter((player) => player.state === "accepted")
		.map((player) => ({
			player: { id: player.id, username: player.username },
			isViewer: player.id === viewerId,
			characters: player.characters.filter((character) => character.approved),
		}))
		.filter((group) => group.characters.length > 0);
	return [...groups.filter((g) => g.isViewer), ...groups.filter((g) => !g.isViewer)];
}

/**
 * What a character is called in a game: its in-game name, or the owner's label
 * for ones that never got a name.
 */
export const characterDisplayName = (character: {
	name: string | null;
	label: string;
}) => character.name || character.label;

/**
 * The owner's private label, shown muted beside the name, but only to the
 * owner and only when it adds something. Null otherwise.
 */
export const ownerLabelHint = (
	character: { name: string | null; label: string },
	isOwner: boolean,
) =>
	isOwner && character.name && character.name !== character.label
		? character.label
		: null;

/**
 * Whether the game's forum link is worth showing: a public game's forum is
 * open to everyone, a private one to its accepted players (GMs included).
 */
export const canReadGameForum = (game: Pick<GameDetails, "public" | "viewer_state">) =>
	game.public || game.viewer_state === "accepted";
