import { describe, expect, it } from "vitest";
import { playingCardFromNumber } from "./deck-cards";

describe("playingCardFromNumber", () => {
	it("maps the suited cards in suit then rank order", () => {
		expect(playingCardFromNumber(0, "pcwoj")).toEqual({ suit: "hearts", rank: "ace" });
		expect(playingCardFromNumber(12, "pcwoj")).toEqual({
			suit: "hearts",
			rank: "king",
		});
		expect(playingCardFromNumber(13, "pcwoj")).toEqual({ suit: "spades", rank: "ace" });
		expect(playingCardFromNumber(26 + 9, "pcwoj")).toEqual({
			suit: "diamonds",
			rank: "10",
		});
		expect(playingCardFromNumber(51, "pcwoj")).toEqual({ suit: "clubs", rank: "king" });
	});

	it("keeps the suits and puts the black then red joker after them in a deck with jokers", () => {
		expect(playingCardFromNumber(51, "pcwj")).toEqual({ suit: "clubs", rank: "king" });
		expect(playingCardFromNumber(52, "pcwj")).toEqual({ suit: "joker", rank: "black" });
		expect(playingCardFromNumber(53, "pcwj")).toEqual({ suit: "joker", rank: "red" });
	});

	it("has no card 52 or 53 in a deck without jokers", () => {
		expect(playingCardFromNumber(52, "pcwoj")).toBeNull();
		expect(playingCardFromNumber(53, "pcwoj")).toBeNull();
	});

	it("rejects numbers past the deck, negatives, and non-integers", () => {
		expect(playingCardFromNumber(54, "pcwj")).toBeNull();
		expect(playingCardFromNumber(-1, "pcwj")).toBeNull();
		expect(playingCardFromNumber(1.5, "pcwj")).toBeNull();
	});

	it("returns null for a deck type that isn't a playing-card deck", () => {
		expect(playingCardFromNumber(0, "tarot")).toBeNull();
	});
});
