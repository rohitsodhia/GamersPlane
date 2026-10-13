import { afterEach, describe, expect, it, vi } from "vitest";
import {
	buildDeck,
	loadGameDeck,
	type StoredDeck,
	saveGameDeck,
	shuffle,
} from "./local-deck";

afterEach(() => {
	localStorage.clear();
	vi.restoreAllMocks();
});

const sortKey = (card: { suit: string; rank: string }) => `${card.suit}:${card.rank}`;

describe("buildDeck", () => {
	it("has 52 cards without jokers", () => {
		const deck = buildDeck("pcwoj");
		expect(deck).toHaveLength(52);
		expect(deck.some((card) => card.suit === "joker")).toBe(false);
	});

	it("adds a black and a red joker with jokers", () => {
		const deck = buildDeck("pcwj");
		expect(deck).toHaveLength(54);
		expect(deck.filter((card) => card.suit === "joker")).toEqual([
			{ suit: "joker", rank: "black" },
			{ suit: "joker", rank: "red" },
		]);
	});
});

describe("shuffle", () => {
	it("keeps the same cards without touching the input", () => {
		const deck = buildDeck("pcwj");
		const before = [...deck];
		const shuffled = shuffle(deck);

		expect(deck).toEqual(before);
		expect(shuffled.map(sortKey).sort()).toEqual(deck.map(sortKey).sort());
	});
});

describe("per-game deck storage", () => {
	const stored: StoredDeck = {
		deckType: "pcwoj",
		deck: [
			{ suit: "hearts", rank: "ace" },
			{ suit: "spades", rank: "10" },
		],
		drawn: [{ suit: "joker", rank: "red" }],
	};

	it("round-trips a deck", () => {
		saveGameDeck(5, stored);
		expect(loadGameDeck(5)).toEqual(stored);
	});

	it("keeps each game's deck separate", () => {
		saveGameDeck(5, stored);
		saveGameDeck(6, { ...stored, deckType: "pcwj" });

		expect(loadGameDeck(5)?.deckType).toBe("pcwoj");
		expect(loadGameDeck(6)?.deckType).toBe("pcwj");
		expect(loadGameDeck(7)).toBeNull();
	});

	it("saving null clears the deck", () => {
		saveGameDeck(5, stored);
		saveGameDeck(5, null);
		expect(loadGameDeck(5)).toBeNull();
	});

	it.each([
		["not JSON", "{oops"],
		["not an object", "42"],
		["unknown deck type", JSON.stringify({ ...stored, deckType: "tarot" })],
		["missing drawn", JSON.stringify({ deckType: "pcwj", deck: [] })],
		[
			"an unknown card",
			JSON.stringify({ ...stored, deck: [{ suit: "stars", rank: "ace" }] }),
		],
		[
			"a bad joker color",
			JSON.stringify({ ...stored, drawn: [{ suit: "joker", rank: "blue" }] }),
		],
	])("treats %s as no deck", (_name, raw) => {
		localStorage.setItem("game-bar:deck:5", raw);
		expect(loadGameDeck(5)).toBeNull();
	});

	it("treats unavailable storage as no deck and doesn't throw on save", () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new Error("blocked");
		});
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("blocked");
		});

		expect(loadGameDeck(5)).toBeNull();
		expect(() => saveGameDeck(5, stored)).not.toThrow();
	});
});
