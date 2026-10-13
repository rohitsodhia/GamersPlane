import { useEffect } from "react";
import { create } from "zustand";

export type SheetPanelTarget = { gameId: number; characterId: number };

type GameBarStore = {
	/** The game the current page belongs to; null shows no game bar. */
	gameId: number | null;
	setGameId: (gameId: number | null) => void;
	/**
	 * The character sheet open in the bar's panel. Scoped to a game rather than
	 * cleared with `gameId`, which blips to null between two pages of one game; the
	 * panel only shows while its game is the current one.
	 */
	panel: SheetPanelTarget | null;
	openPanel: (gameId: number, characterId: number) => void;
	closePanel: () => void;
	/** The panel's chosen height in px; null is the default share of the viewport. */
	panelHeight: number | null;
	setPanelHeight: (height: number | null) => void;
};

export const useGameBarStore = create<GameBarStore>()((set) => ({
	gameId: null,
	// Landing on a different game drops the old game's panel for good; a null
	// (the gap between pages) leaves it alone.
	setGameId: (gameId) =>
		set((state) => ({
			gameId,
			panel: gameId !== null && state.panel?.gameId !== gameId ? null : state.panel,
		})),
	panel: null,
	openPanel: (gameId, characterId) => set({ panel: { gameId, characterId } }),
	closePanel: () => set({ panel: null }),
	panelHeight: null,
	setPanelHeight: (panelHeight) => set({ panelHeight }),
}));

/** The character open in the panel for this game, or null. */
export const selectPanelCharacterId = (gameId: number) => (state: GameBarStore) =>
	state.panel?.gameId === gameId ? state.panel.characterId : null;

/**
 * Called by a page that belongs to a game: the root layout's game bar shows
 * for it while the page is mounted. Pass null while the game isn't known (or
 * the page isn't in one).
 */
export function useGameBarGame(gameId: number | null) {
	const setGameId = useGameBarStore((state) => state.setGameId);
	useEffect(() => {
		setGameId(gameId);
		return () => setGameId(null);
	}, [gameId, setGameId]);
}
