import { useEffect } from "react";
import { create } from "zustand";

type GameBarStore = {
	/** The game the current page belongs to; null shows no game bar. */
	gameId: number | null;
	setGameId: (gameId: number | null) => void;
};

export const useGameBarStore = create<GameBarStore>()((set) => ({
	gameId: null,
	setGameId: (gameId) => set({ gameId }),
}));

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
