import type { JokerCardProps, SuitCardProps } from "#/components/DeckCard";
import { RANKS, SUITS } from "#/lib/deck-cards";

export type DeckType = "pcwj" | "pcwoj";
export type Card = SuitCardProps | JokerCardProps;

export const DECK_TYPE_LABELS: Record<DeckType, string> = {
	pcwj: "Playing Cards w/ Jokers",
	pcwoj: "Playing Cards w/o Jokers",
};

export function buildDeck(deckType: DeckType): Card[] {
	const cards: Card[] = [];
	for (const suit of SUITS) {
		for (const rank of RANKS) {
			cards.push({ suit, rank });
		}
	}
	if (deckType === "pcwj") {
		cards.push({ suit: "joker", rank: "black" });
		cards.push({ suit: "joker", rank: "red" });
	}
	return cards;
}

export function shuffle<T>(items: T[]): T[] {
	const shuffled = [...items];
	for (let i = shuffled.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
	}
	return shuffled;
}

/** A deck as the game bar keeps it: what's left (in order) and the last hand drawn. */
export type StoredDeck = {
	deckType: DeckType;
	deck: Card[];
	drawn: Card[];
};

const storageKey = (gameId: number) => `game-bar:deck:${gameId}`;

const SUIT_NAMES = new Set<string>(SUITS);
const RANK_NAMES = new Set<string>(RANKS);

function isCard(value: unknown): value is Card {
	if (typeof value !== "object" || value === null) return false;
	const { suit, rank } = value as { suit?: unknown; rank?: unknown };
	if (suit === "joker") return rank === "black" || rank === "red";
	return (
		typeof suit === "string" &&
		SUIT_NAMES.has(suit) &&
		typeof rank === "string" &&
		RANK_NAMES.has(rank)
	);
}

const isCardList = (value: unknown): value is Card[] =>
	Array.isArray(value) && value.every(isCard);

/** The game's saved deck, or null when there is none or it can't be trusted. */
export function loadGameDeck(gameId: number): StoredDeck | null {
	try {
		const raw = localStorage.getItem(storageKey(gameId));
		if (raw === null) return null;
		const parsed: unknown = JSON.parse(raw);
		if (typeof parsed !== "object" || parsed === null) return null;
		const { deckType, deck, drawn } = parsed as Record<string, unknown>;
		if (deckType !== "pcwj" && deckType !== "pcwoj") return null;
		if (!isCardList(deck) || !isCardList(drawn)) return null;
		return { deckType, deck, drawn };
	} catch {
		return null;
	}
}

export function saveGameDeck(gameId: number, stored: StoredDeck | null) {
	try {
		if (stored === null) localStorage.removeItem(storageKey(gameId));
		else localStorage.setItem(storageKey(gameId), JSON.stringify(stored));
	} catch {
		// Storage unavailable or full: the deck still works for this visit.
	}
}
