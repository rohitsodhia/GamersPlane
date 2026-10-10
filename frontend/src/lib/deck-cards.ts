import type {
	CardRank,
	CardSuit,
	JokerCardProps,
	SuitCardProps,
} from "#/components/DeckCard";

// Suit order of a deck and rank order within a suit; matches the card sprite.
export const SUITS: readonly CardSuit[] = ["hearts", "spades", "diamonds", "clubs"];
export const RANKS: readonly CardRank[] = [
	"ace",
	"2",
	"3",
	"4",
	"5",
	"6",
	"7",
	"8",
	"9",
	"10",
	"jack",
	"queen",
	"king",
];

export type PlayingCard = SuitCardProps | JokerCardProps;

// Cards are numbered by their position in a fresh deck (0-based, as the API stores
// them): suits in `SUITS` order with `RANKS` within each, then the black and red
// jokers for decks that have them. The legacy site numbered the same way from 1.
// Returns null for a number the deck doesn't have or an unknown deck type.
export function playingCardFromNumber(
	card: number,
	deckType: string,
): PlayingCard | null {
	if (deckType !== "pcwj" && deckType !== "pcwoj") return null;
	if (!Number.isInteger(card) || card < 0) return null;

	const suited = SUITS.length * RANKS.length;
	if (card < suited) {
		return {
			suit: SUITS[Math.floor(card / RANKS.length)],
			rank: RANKS[card % RANKS.length],
		};
	}
	if (deckType === "pcwj") {
		if (card === suited) return { suit: "joker", rank: "black" };
		if (card === suited + 1) return { suit: "joker", rank: "red" };
	}
	return null;
}
