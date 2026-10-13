import clsx from "clsx";
import { useEffect, useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import {
	buildDeck,
	DECK_TYPE_LABELS,
	type DeckType,
	loadGameDeck,
	type StoredDeck,
	saveGameDeck,
	shuffle,
} from "#/lib/local-deck";
import BarPopover from "./BarPopover";
import DeckCard from "./DeckCard";
import styles from "./GameBarTools.module.css";

// One deck per game, kept in this browser's localStorage (see `local-deck`) so it
// survives a reload until a new deck is started. Mount it with `key={gameId}` so
// switching games shows that game's deck.
export default function CardsMenu({ gameId }: { gameId: number }) {
	const [stored, setStored] = useState<StoredDeck | null>(null);
	const [numToDraw, setNumToDraw] = useState("1");

	// After mount, not in the initial state: the server render has no storage, and
	// the first client render has to match it.
	useEffect(() => {
		setStored(loadGameDeck(gameId));
	}, [gameId]);

	function update(next: StoredDeck | null) {
		setStored(next);
		saveGameDeck(gameId, next);
	}

	function startNewDeck(deckType: DeckType) {
		update({ deckType, deck: shuffle(buildDeck(deckType)), drawn: [] });
		setNumToDraw("1");
	}

	const requestedDraw = Number.parseInt(numToDraw, 10) || 0;

	function drawCards() {
		if (!stored || requestedDraw < 1) return;
		const count = Math.min(requestedDraw, stored.deck.length);
		update({
			...stored,
			deck: stored.deck.slice(count),
			drawn: stored.deck.slice(0, count),
		});
	}

	return (
		<BarPopover label="Cards" placement="top end" dialogClassName={styles["tool"]}>
			{stored ? (
				<>
					<p className={styles["deck-name"]}>{DECK_TYPE_LABELS[stored.deckType]}</p>
					<p className={styles["cards-left"]}>
						Cards Left: <span>{stored.deck.length}</span>
					</p>
					<form
						className={styles["draw-form"]}
						onSubmit={(e) => {
							e.preventDefault();
							drawCards();
						}}
					>
						Draw
						<TextField
							aria-label="Cards to draw"
							value={numToDraw}
							onChange={(value) => setNumToDraw(value.replace(/\D/g, ""))}
							autoComplete="off"
						>
							<Input maxLength={2} />
						</TextField>
						Cards
						<div className={styles["draw-actions"]}>
							<Button
								type="submit"
								className={clsx("skew-btn", styles["skew"])}
								isDisabled={stored.deck.length === 0 || requestedDraw < 1}
							>
								Draw Cards
							</Button>
							<Button
								className={clsx("skew-btn", styles["skew"])}
								onPress={() => {
									update(null);
									setNumToDraw("1");
								}}
							>
								New Deck
							</Button>
						</div>
					</form>
					{stored.drawn.length > 0 && (
						<div className={styles["drawn"]}>
							{stored.drawn.map((card, i) => (
								// biome-ignore lint/suspicious/noArrayIndexKey: cards are not unique and order matters, not identity
								<DeckCard key={i} {...card} size="mid" />
							))}
						</div>
					)}
				</>
			) : (
				<div className={styles["deck-choices"]}>
					<p className={styles["deck-name"]}>New Deck</p>
					{(Object.keys(DECK_TYPE_LABELS) as DeckType[]).map((type) => (
						<Button
							key={type}
							className={styles["small-btn"]}
							onPress={() => startNewDeck(type)}
						>
							{DECK_TYPE_LABELS[type]}
						</Button>
					))}
				</div>
			)}
		</BarPopover>
	);
}
