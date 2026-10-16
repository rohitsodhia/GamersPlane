// "Full" whenever the game has no free slot. Uses >= because prod has games that
// are over capacity (e.g. 7 of 5).
export const playersLabel = (game: { player_count: number; num_players: number }) =>
	game.player_count >= game.num_players
		? "Full"
		: `${game.player_count}/${game.num_players} players`;
