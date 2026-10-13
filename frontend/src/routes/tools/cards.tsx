import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import DeckCard from "#/components/DeckCard";
import {
	buildDeck,
	type Card,
	DECK_TYPE_LABELS,
	type DeckType,
	shuffle,
} from "#/lib/local-deck";
import { useHbMargined } from "#/lib/use-hb-margined";
import styles from "./cards.module.css";

export const Route = createFileRoute("/tools/cards")({
	component: RouteComponent,
});

function RouteComponent() {
	const [deckType, setDeckType] = useState<DeckType | null>(null);
	const [deck, setDeck] = useState<Card[]>([]);
	const [drawnCards, setDrawnCards] = useState<Card[]>([]);
	const [numToDraw, setNumToDraw] = useState("1");

	function startNewDeck(type: DeckType) {
		setDeckType(type);
		setDeck(shuffle(buildDeck(type)));
		setDrawnCards([]);
		setNumToDraw("1");
	}

	const requestedDraw = Number.parseInt(numToDraw, 10) || 0;

	function drawCards() {
		if (requestedDraw < 1) return;
		const count = Math.min(requestedDraw, deck.length);
		setDrawnCards(deck.slice(0, count));
		setDeck(deck.slice(count));
	}

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Card Dealer
			</h1>

			<div
				className={styles["main-wrapper"]}
				style={{ marginInline: `${hbMargined.margin}px` }}
			>
				<div className={styles.controls}>
					{!deckType && (
						<div className={styles["new-deck"]}>
							<h2>New Deck</h2>
							<div>
								<button type="button" onClick={() => startNewDeck("pcwj")}>
									Playing Cards w/ Jokers
								</button>
							</div>
							<div>
								<button type="button" onClick={() => startNewDeck("pcwoj")}>
									Playing Cards w/o Jokers
								</button>
							</div>
						</div>
					)}
					{deckType && (
						<form
							className={styles["card-controls"]}
							onSubmit={(e) => {
								e.preventDefault();
								drawCards();
							}}
						>
							<p className={styles["deck-name"]}>{DECK_TYPE_LABELS[deckType]}</p>
							<p>
								Cards Left: <span>{deck.length}</span>
							</p>
							<div>
								Draw{" "}
								<input
									type="text"
									maxLength={2}
									value={numToDraw}
									autoComplete="off"
									className={styles["num-cards"]}
									onChange={(e) => setNumToDraw(e.target.value.replace(/\D/g, ""))}
								/>{" "}
								Cards
							</div>
							<div className="align-center">
								<button
									type="submit"
									className="skew-btn"
									disabled={deck.length === 0 || requestedDraw < 1}
								>
									Draw Cards
								</button>
							</div>
							<div className="align-center">
								<button
									type="button"
									className="skew-btn"
									onClick={() => setDeckType(null)}
								>
									New Deck
								</button>
							</div>
						</form>
					)}
				</div>
				<div className={styles["card-space"]}>
					{drawnCards.map((card, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: cards are not unique and order matters, not identity
						<DeckCard key={i} {...card} />
					))}
				</div>
			</div>
		</div>
	);
}
