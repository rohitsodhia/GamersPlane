import styles from "./DeckCard.module.css";

export type CardSuit = "hearts" | "spades" | "diamonds" | "clubs";
export type CardRank =
	| "ace"
	| "2"
	| "3"
	| "4"
	| "5"
	| "6"
	| "7"
	| "8"
	| "9"
	| "10"
	| "jack"
	| "queen"
	| "king";
export type JokerColor = "black" | "red";

export type SuitCardProps = { suit: CardSuit; rank: CardRank };
export type JokerCardProps = { suit: "joker"; rank: JokerColor };

export type DeckCardProps = (SuitCardProps | JokerCardProps) & {
	mini?: boolean;
	faceDown?: boolean;
};

const CARD_WIDTH = 100;
const CARD_HEIGHT = 125;
const SHEET_COLS = 13;
const SHEET_ROWS = 5;
const MINI_SCALE = 0.48; // 100x125 -> 48x60

// Row order in the sprite sheet: hearts, spades, diamonds, clubs, joker
const SUIT_ROWS: Record<CardSuit | "joker", number> = {
	hearts: 0,
	spades: 1,
	diamonds: 2,
	clubs: 3,
	joker: 4,
};

// Column order in the sprite sheet: ace, 2-10, jack, queen, king
const RANK_COLS: Record<CardRank, number> = {
	ace: 0,
	"2": 1,
	"3": 2,
	"4": 3,
	"5": 4,
	"6": 5,
	"7": 6,
	"8": 7,
	"9": 8,
	"10": 9,
	jack: 10,
	queen: 11,
	king: 12,
};

// Column order for jokers: black, then red
const JOKER_COLS: Record<JokerColor, number> = {
	black: 0,
	red: 1,
};

const RANK_LABELS: Record<CardRank, string> = {
	ace: "Ace",
	"2": "2",
	"3": "3",
	"4": "4",
	"5": "5",
	"6": "6",
	"7": "7",
	"8": "8",
	"9": "9",
	"10": "10",
	jack: "Jack",
	queen: "Queen",
	king: "King",
};

const SUIT_LABELS: Record<CardSuit, string> = {
	hearts: "Hearts",
	spades: "Spades",
	diamonds: "Diamonds",
	clubs: "Clubs",
};

function getLabel(props: SuitCardProps | JokerCardProps): string {
	if (props.suit === "joker") {
		return `${props.rank === "red" ? "Red" : "Black"} Joker`;
	}
	return `${RANK_LABELS[props.rank]} of ${SUIT_LABELS[props.suit]}`;
}

function DeckCard(props: DeckCardProps) {
	const { mini = false, faceDown = false } = props;
	const scale = mini ? MINI_SCALE : 1;
	const width = CARD_WIDTH * scale;
	const height = CARD_HEIGHT * scale;

	if (faceDown) {
		return (
			<div className={styles.window} style={{ width, height }}>
				<img
					src="/images/cards/back.png"
					alt="Face-down card"
					title="Face-down card"
					className={styles.back}
				/>
			</div>
		);
	}

	const label = getLabel(props);
	const row = props.suit === "joker" ? SUIT_ROWS.joker : SUIT_ROWS[props.suit];
	const col = props.suit === "joker" ? JOKER_COLS[props.rank] : RANK_COLS[props.rank];

	return (
		<div className={styles.window} style={{ width, height }}>
			<img
				src="/images/cards/pc.png"
				alt={label}
				title={label}
				className={styles.sprite}
				style={{
					width: CARD_WIDTH * SHEET_COLS * scale,
					height: CARD_HEIGHT * SHEET_ROWS * scale,
					top: -row * height,
					left: -col * width,
				}}
			/>
		</div>
	);
}

export default DeckCard;
