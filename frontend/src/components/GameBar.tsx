import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "@tanstack/react-router";
import { Button } from "react-aria-components";
import { gameDetailsQueryOptions } from "#/queries/game";
import { meQueryOptions } from "#/queries/me";
import { useAuthStore } from "#/stores/auth";
import { selectPanelCharacterId, useGameBarStore } from "#/stores/game-bar";
import BarPopover from "./BarPopover";
import styles from "./GameBar.module.css";
import CardsMenu from "./GameBarCards";
import DiceMenu from "./GameBarDice";
import {
	approvedCharacterGroups,
	type CharacterGroup,
	canReadGameForum,
	characterDisplayName,
} from "./game-bar";
import SheetPanel from "./SheetPanel";
import { panelHeightCss } from "./sheet-panel";

// A bar fixed to the bottom of game-related pages (those that call
// `useGameBarGame`). Left cluster: where the game lives and its characters; a
// right cluster holds the dice and card tools.
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
	const panelCharacterId = useGameBarStore(selectPanelCharacterId(gameId));
	const panelHeight = useGameBarStore((state) => state.panelHeight);

	// No access (or still loading): no bar.
	if (!game) return null;

	const groups = approvedCharacterGroups(game.players, me?.id ?? null);
	const panelCharacter = groups
		.flatMap((group) => group.characters)
		.find((character) => character.id === panelCharacterId);
	const panelLabel = panelCharacter && characterDisplayName(panelCharacter);
	// A link to where you already are is dropped: Game Details on the details page,
	// Forums anywhere in the forums (threads and posting included).
	const onDetails = new RegExp(`^/games/${gameId}/?$`).test(pathname);
	const onForum = pathname === "/forums" || pathname.startsWith("/forums/");

	return (
		<>
			{/* Keeps the end of the page clear of the fixed bar, and of the sheet panel
			    while it's open. */}
			<div
				className={styles["spacer"]}
				style={
					panelCharacterId === null
						? undefined
						: {
								height: `calc(var(--game-bar-height) + ${panelHeightCss(panelHeight)})`,
							}
				}
				aria-hidden="true"
			/>
			<SheetPanel gameId={gameId} fallbackLabel={panelLabel} />
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
						{groups.length > 0 && <CharactersMenu gameId={gameId} groups={groups} />}
					</div>
					<div className={styles["cluster"]}>
						<DiceMenu />
						<CardsMenu key={gameId} gameId={gameId} />
					</div>
				</div>
			</nav>
		</>
	);
}

function CharactersMenu({
	gameId,
	groups,
}: {
	gameId: number;
	groups: CharacterGroup[];
}) {
	const openPanel = useGameBarStore((state) => state.openPanel);
	const panelCharacterId = useGameBarStore(selectPanelCharacterId(gameId));

	// A list of links and plain text rather than a RAC Menu: menu items would
	// navigate with a full page load (no RAC router provider), and the
	// unviewable characters aren't actions at all.
	return (
		<BarPopover
			label="Characters"
			placement="top start"
			dialogClassName={styles["characters"]}
		>
			{(close) =>
				groups.map((group) => (
					<section key={group.player.id} className={styles["group"]}>
						<h3 className={styles["group-title"]}>
							{group.isViewer ? "Your characters" : group.player.username}
						</h3>
						<ul className={styles["character-list"]}>
							{group.characters.map((character) => (
								<li key={character.id} className={styles["character"]}>
									{character.can_view ? (
										<Button
											className={styles["character-button"]}
											aria-current={
												panelCharacterId === character.id ? "true" : undefined
											}
											onPress={() => {
												openPanel(gameId, character.id);
												close();
											}}
										>
											{characterDisplayName(character)}
										</Button>
									) : (
										<span>{characterDisplayName(character)}</span>
									)}
									{character.type === "npc" && (
										<span className={styles["npc-tag"]}>NPC</span>
									)}
								</li>
							))}
						</ul>
					</section>
				))
			}
		</BarPopover>
	);
}
