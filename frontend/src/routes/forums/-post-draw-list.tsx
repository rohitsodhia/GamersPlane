import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Eye, EyeOff } from "lucide-react";
import DeckCard from "#/components/DeckCard";
import { ApiError } from "#/lib/api";
import { playingCardFromNumber } from "#/lib/deck-cards";
import { type PostDraw, toggleDrawCard, withUpdatedDraw } from "#/queries/posts";
import styles from "./-post-draw-list.module.css";

function CardFace({ card, deckType }: { card: number | null; deckType: string }) {
	if (card === null) return <DeckCard suit="clubs" rank="ace" size="mid" faceDown />;
	const face = playingCardFromNumber(card, deckType);
	if (!face) return <div className={styles["unknown-card"]}>Card {card}</div>;
	return <DeckCard {...face} size="mid" />;
}

function DrawItem({
	postId,
	threadId,
	draw,
	isAuthor,
	canToggle,
}: {
	postId: number;
	threadId: number;
	draw: PostDraw;
	isAuthor: boolean;
	canToggle: boolean;
}) {
	const queryClient = useQueryClient();
	const toggle = useMutation({
		mutationFn: (index: number) => toggleDrawCard(postId, draw.id, index),
		onSuccess: (updated) => {
			queryClient.setQueriesData<Parameters<typeof withUpdatedDraw>[0]>(
				{ queryKey: ["posts", threadId] },
				(cached) => withUpdatedDraw(cached, postId, updated),
			);
		},
	});

	return (
		<li className={styles["draw"]}>
			<div className={styles["draw-header"]}>
				{draw.reason}
				<span className={styles["deck-label"]}>
					{draw.reason && " · "}
					{draw.deck_label}
				</span>
			</div>
			<div className={styles["cards"]}>
				{draw.cards.map((card, index) => {
					const revealed = draw.revealed[index];
					return (
						// biome-ignore lint/suspicious/noArrayIndexKey: cards are positional and can repeat
						<div key={index} className={styles["card"]}>
							{!isAuthor ? (
								<CardFace card={revealed ? card : null} deckType={draw.deck_type} />
							) : (
								<>
									<button
										type="button"
										className={styles["card-toggle"]}
										aria-label={`${revealed ? "Hide" : "Reveal"} card ${index + 1}`}
										disabled={!canToggle || toggle.isPending}
										onClick={() => toggle.mutate(index)}
									>
										<CardFace card={card} deckType={draw.deck_type} />
									</button>
									<span
										className={clsx(
											styles["eye-badge"],
											revealed ? styles["eye-revealed"] : styles["eye-hidden"],
										)}
										aria-hidden="true"
									>
										{revealed ? <Eye size={12} /> : <EyeOff size={12} />}
									</span>
								</>
							)}
						</div>
					);
				})}
			</div>
			{toggle.isError && (
				<div className="error">
					{toggle.error instanceof ApiError
						? toggle.error.errors.map((e) => e.detail).join(", ")
						: "Couldn't change that card."}
				</div>
			)}
		</li>
	);
}

export function PostDrawList({
	postId,
	threadId,
	draws,
	isAuthor,
	canToggle,
}: {
	postId: number;
	threadId: number;
	draws: PostDraw[];
	// The author sees every card and can reveal or hide each one.
	isAuthor: boolean;
	// False when the thread is locked and the author can't moderate it.
	canToggle: boolean;
}) {
	if (draws.length === 0) return null;
	return (
		<div className={styles["draws"]}>
			<h4>Deck Draws</h4>
			<ul>
				{draws.map((draw) => (
					<DrawItem
						key={draw.id}
						postId={postId}
						threadId={threadId}
						draw={draw}
						isAuthor={isAuthor}
						canToggle={canToggle}
					/>
				))}
			</ul>
		</div>
	);
}
