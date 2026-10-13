import { afterEach, describe, expect, it } from "vitest";
import { selectPanelCharacterId, useGameBarStore } from "./game-bar";

afterEach(() => {
	useGameBarStore.setState({ gameId: null, panel: null, panelHeight: null });
});

describe("sheet panel scoping", () => {
	it("shows only for the game it was opened in", () => {
		const { openPanel } = useGameBarStore.getState();
		openPanel(5, 11);

		expect(selectPanelCharacterId(5)(useGameBarStore.getState())).toBe(11);
		expect(selectPanelCharacterId(6)(useGameBarStore.getState())).toBeNull();
	});

	it("survives the null gameId between two pages of the same game", () => {
		const store = useGameBarStore.getState();
		store.setGameId(5);
		store.openPanel(5, 11);

		store.setGameId(null);
		store.setGameId(5);

		expect(useGameBarStore.getState().panel).toEqual({ gameId: 5, characterId: 11 });
	});

	it("is dropped on landing in a different game", () => {
		const store = useGameBarStore.getState();
		store.setGameId(5);
		store.openPanel(5, 11);

		store.setGameId(null);
		store.setGameId(6);
		store.setGameId(null);
		store.setGameId(5);

		expect(useGameBarStore.getState().panel).toBeNull();
	});
});
