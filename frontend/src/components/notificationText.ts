const plural = (count: number, singular: string) =>
	`${count} ${singular}${count === 1 ? "" : "s"}`;

/**
 * The bell line for a game with things waiting on its GM, e.g.
 * "2 players and 1 character pending in Campaign". A zero count is left out.
 */
export function pendingText(
	players: number,
	characters: number,
	title: string,
): string {
	const parts = [
		players > 0 ? plural(players, "player") : null,
		characters > 0 ? plural(characters, "character") : null,
	].filter((part) => part !== null);
	return `${parts.join(" and ")} pending in ${title}`;
}
