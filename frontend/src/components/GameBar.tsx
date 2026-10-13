import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "@tanstack/react-router";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import { gameDetailsQueryOptions } from "#/queries/game";
import { meQueryOptions } from "#/queries/me";
import { useAuthStore } from "#/stores/auth";
import { useGameBarStore } from "#/stores/game-bar";
import styles from "./GameBar.module.css";
import {
	approvedCharacterGroups,
	type CharacterGroup,
	canReadGameForum,
} from "./game-bar";

// A bar fixed to the bottom of game-related pages (those that call
// `useGameBarGame`). Left cluster: where the game lives and its characters; a
// right cluster is the spot for the later tools menu.
export default function GameBar() {
	const gameId = useGameBarStore((state) => state.gameId);
	if (gameId === null) return null;
	return <GameBarContent gameId={gameId} />;
}

function GameBarContent({ gameId }: { gameId: number }) {
	const token = useAuthStore((state) => state.token);
	const { data: game } = useQuery(gameDetailsQueryOptions(gameId));
	const { data: me } = useQuery({ ...meQueryOptions, enabled: !!token });
	const pathname = useLocation({ select: (location) => location.pathname });

	// No access (or still loading): no bar.
	if (!game) return null;

	const groups = approvedCharacterGroups(game.players, me?.id ?? null);
	// A link to where you already are is dropped: Game Details on the details page,
	// Forums anywhere in the forums (threads and posting included).
	const onDetails = new RegExp(`^/games/${gameId}/?$`).test(pathname);
	const onForum = pathname === "/forums" || pathname.startsWith("/forums/");

	return (
		<>
			{/* Keeps the end of the page clear of the fixed bar. */}
			<div className={styles["spacer"]} aria-hidden="true" />
			<nav className={styles["bar"]} aria-label="Game">
				<div className={styles["content"]}>
					<div className={styles["cluster"]}>
						{!onDetails && (
							<Link
								to="/games/$gameId"
								params={{ gameId }}
								className={styles["title"]}
								title={game.title}
							>
								Game Details
							</Link>
						)}
						{!onForum && canReadGameForum(game) && (
							<Link
								to="/forums/{-$forumId}"
								params={{ forumId: game.root_forum_id }}
								className={styles["item"]}
							>
								Forums
							</Link>
						)}
						{groups.length > 0 && <CharactersMenu groups={groups} />}
					</div>
				</div>
			</nav>
		</>
	);
}

function CharactersMenu({ groups }: { groups: CharacterGroup[] }) {
	const [open, setOpen] = useState(false);
	const triggerRef = useRef<HTMLButtonElement>(null);
	const popoverRef = useRef<HTMLElement>(null);

	// A list of links and plain text rather than a RAC Menu: menu items would
	// navigate with a full page load (no RAC router provider), and the
	// unviewable characters aren't actions at all. Non-modal so opening it
	// doesn't lock page scrolling (see `ActionsMenu`), which means an outside
	// press and Escape close it by hand.
	useEffect(() => {
		if (!open) return;
		const closeOnOutsidePress = (e: PointerEvent) => {
			const target = e.target as Node;
			if (popoverRef.current?.contains(target)) return;
			if (triggerRef.current?.contains(target)) return;
			setOpen(false);
		};
		const closeOnEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape") setOpen(false);
		};
		document.addEventListener("pointerdown", closeOnOutsidePress);
		document.addEventListener("keydown", closeOnEscape);
		return () => {
			document.removeEventListener("pointerdown", closeOnOutsidePress);
			document.removeEventListener("keydown", closeOnEscape);
		};
	}, [open]);

	// A non-modal RAC popover closes itself on blur, so pressing the trigger while
	// it's open closes it (focus leaves the dialog) and then the press toggles it
	// straight back open. Remember it was open when the press began and swallow
	// that reopen, so the trigger toggles.
	const wasOpenAtPress = useRef(false);
	const handleOpenChange = (next: boolean) => {
		if (next && wasOpenAtPress.current) {
			wasOpenAtPress.current = false;
			return;
		}
		setOpen(next);
	};

	return (
		<DialogTrigger isOpen={open} onOpenChange={handleOpenChange}>
			<Button
				ref={triggerRef}
				className={styles["item"]}
				onPressStart={() => {
					wasOpenAtPress.current = open;
				}}
			>
				Characters
			</Button>
			<Popover
				ref={popoverRef}
				// Keep RAC's default class too: it carries the shared floating-panel surface.
				className={clsx("react-aria-Popover", styles["popover"])}
				placement="top start"
				// The trigger fills the bar's height, so 1px clears the bar's top border
				// and the popover sits on it.
				offset={1}
				isNonModal
			>
				<Dialog className={styles["characters"]} aria-label="Characters">
					{groups.map((group) => (
						<section key={group.player.id} className={styles["group"]}>
							<h3 className={styles["group-title"]}>
								{group.isViewer ? "Your characters" : group.player.username}
							</h3>
							<ul className={styles["character-list"]}>
								{group.characters.map((character) => (
									<li key={character.id} className={styles["character"]}>
										{character.can_view ? (
											<Link
												to="/characters/$characterId"
												params={{ characterId: character.id }}
												onClick={() => setOpen(false)}
											>
												{character.label}
											</Link>
										) : (
											<span>{character.label}</span>
										)}
										{character.type === "npc" && (
											<span className={styles["npc-tag"]}>NPC</span>
										)}
									</li>
								))}
							</ul>
						</section>
					))}
				</Dialog>
			</Popover>
		</DialogTrigger>
	);
}
