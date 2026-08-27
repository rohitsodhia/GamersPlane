import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useRef, useState } from "react";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import type { DeckType } from "#/queries/deckTypes";
import type { Deck, GamePlayer } from "#/queries/game";
import { createDeck, updateDeck } from "#/queries/game";
import styles from "./-deck-form-popover.module.css";

type DeckFormPopoverProps = {
	id: string;
	gameId: number;
	deck?: Deck;
	players: GamePlayer[];
	deckTypes: DeckType[];
};

function DeckFormPopover({
	id,
	gameId,
	deck,
	players,
	deckTypes,
}: DeckFormPopoverProps) {
	const popoverRef = useRef<HTMLDivElement>(null);
	const queryClient = useQueryClient();
	const isEdit = !!deck;
	const gmIds = players.filter((player) => player.is_gm).map((player) => player.id);

	const initialPermissions = () => new Set([...(deck?.permissions ?? []), ...gmIds]);

	const [label, setLabel] = useState(deck?.label ?? "");
	const [type, setType] = useState(deck?.type ?? deckTypes[0]?.short ?? "");
	const [permissions, setPermissions] = useState<Set<number>>(initialPermissions);
	const [error, setError] = useState<string | null>(null);

	// Popovers don't unmount between opens, so local edits (or a stale error)
	// from a previous open would otherwise leak into the next one.
	const resetState = () => {
		setLabel(deck?.label ?? "");
		setType(deck?.type ?? deckTypes[0]?.short ?? "");
		setPermissions(initialPermissions());
		setError(null);
	};

	const mutation = useMutation({
		mutationFn: () => {
			const payload = { label, type, permissions: Array.from(permissions) };
			return isEdit
				? updateDeck(gameId, deck.id, payload)
				: createDeck(gameId, payload);
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["decks", gameId] });
			popoverRef.current?.hidePopover();
		},
		onError: (err: unknown) => {
			if (err instanceof ApiError && err.errors[0]?.detail) {
				setError(err.errors[0].detail);
			} else {
				setError("Failed to save deck");
			}
		},
	});

	const togglePermission = (userId: number) => {
		setPermissions((prev) => {
			const next = new Set(prev);
			if (next.has(userId)) {
				next.delete(userId);
			} else {
				next.add(userId);
			}
			return next;
		});
	};

	const hbMargin = useHbMargined<HTMLHeadingElement>();

	return (
		<div
			id={id}
			ref={popoverRef}
			popover="auto"
			className={styles["deck-popover"]}
			onToggle={(e) => {
				if (e.newState === "open") resetState();
			}}
		>
			<h2
				id="deck-popover-title"
				className={clsx("headerbar", styles.title)}
				ref={hbMargin.ref}
			>
				{isEdit ? "Edit Deck" : "New Deck"}
			</h2>
			<form
				onSubmit={(e) => {
					e.preventDefault();
					setError(null);
					mutation.mutate();
				}}
				style={{ marginInline: hbMargin.margin }}
			>
				<div className={styles.field}>
					<label htmlFor={`${id}-label`} className={styles["field-header"]}>
						Deck Label
					</label>
					<input
						id={`${id}-label`}
						type="text"
						maxLength={50}
						value={label}
						onChange={(e) => setLabel(e.target.value)}
						required
					/>
				</div>

				<div className={styles.field}>
					<div className={styles["field-header"]}>
						<span>Deck Type</span>
						{isEdit && (
							<span className={styles.notice}>
								Changing deck types will shuffle the deck.
							</span>
						)}
					</div>
					{deckTypes.map((deckType) => (
						<label key={deckType.short} className={styles["radio-row"]}>
							<input
								type="radio"
								name={`${id}-type`}
								value={deckType.short}
								checked={type === deckType.short}
								onChange={() => setType(deckType.short)}
							/>
							{deckType.name}
						</label>
					))}
				</div>

				<div className={styles.field}>
					<div className={styles["field-header"]}>
						<span>Allow Access</span>
						<div>
							<button
								type="button"
								className={styles["inline-action"]}
								onClick={() =>
									setPermissions(new Set(players.map((player) => player.id)))
								}
							>
								[ Check All ]
							</button>{" "}
							<button
								type="button"
								className={styles["inline-action"]}
								onClick={() => setPermissions(new Set(gmIds))}
							>
								[ Uncheck All ]
							</button>
						</div>
					</div>
					<ul className={styles["permission-list"]}>
						{players.map((player) => (
							<li key={player.id}>
								<label>
									<input
										type="checkbox"
										checked={permissions.has(player.id)}
										disabled={player.is_gm}
										onChange={() => togglePermission(player.id)}
									/>
									{player.username}
								</label>
							</li>
						))}
					</ul>
				</div>

				{error && <div className="error">{error}</div>}

				<div className="align-center">
					<button
						type="submit"
						className="skew-btn"
						disabled={mutation.isPending || !type}
					>
						{isEdit ? "Save" : "Create"}
					</button>{" "}
					<button
						type="button"
						className="skew-btn"
						onClick={() => popoverRef.current?.hidePopover()}
					>
						Cancel
					</button>
				</div>
			</form>
		</div>
	);
}

export default DeckFormPopover;
