import { useMutation, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { favoriteGame, type GameListItem, gamesQueryOptions } from "#/queries/game";
import styles from "./index.module.css";

export const Route = createFileRoute("/games/")({
	beforeLoad: requireAuth,
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(gamesQueryOptions({ mine: true })),
			location,
		),
	component: RouteComponent,
});

function RouteComponent() {
	const { data: games } = useSuspenseQuery(gamesQueryOptions({ mine: true }));

	const [favoriteOverrides, setFavoriteOverrides] = useState<Record<number, boolean>>(
		{},
	);
	const favoriteMutation = useMutation({
		mutationFn: (gameId: number) => favoriteGame(gameId),
		onSuccess: (data, gameId) =>
			setFavoriteOverrides((prev) => ({ ...prev, [gameId]: data.favorite })),
	});

	const playing = games.filter((game) => !game.is_gm && !game.is_retired);
	const running = games.filter((game) => game.is_gm && !game.is_retired);
	const retired = games.filter((game) => game.is_retired);

	const playingHb = useHbMargined<HTMLHeadingElement>();
	const runningHb = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar">
				<i className="ra ra-gamers-plane" /> My Games
			</h1>

			<div id="games-playing">
				<div className="hb-topper">
					<div className="trapezoid red-trapezoid">
						<Link to="/forums/{-$forumId}" params={{ forumId: 10 }}>
							Visit the Games Tavern
						</Link>
						<Link to="/games/list">Browse games</Link>
					</div>
				</div>
				<h2 className="headerbar hb-dark has-topper" ref={playingHb.ref}>
					Games I'm Playing
				</h2>
				{playing.length > 0 ? (
					<ul
						className={styles["game-list"]}
						style={{ marginInline: playingHb.margin }}
					>
						{playing.map((game) => (
							<GameRow
								key={game.id}
								game={game}
								favorited={favoriteOverrides[game.id] ?? game.favorited}
								onToggleFavorite={() => favoriteMutation.mutate(game.id)}
								pending={
									favoriteMutation.isPending && favoriteMutation.variables === game.id
								}
							/>
						))}
					</ul>
				) : (
					<div className={styles.notice} style={{ marginInline: playingHb.margin }}>
						It seems you aren't playing any games yet.
						<br />
						You might want to <a href="/forums/">find one in the Games Tavern</a>.
					</div>
				)}
			</div>

			<div id="games-running">
				<div className="hb-topper">
					<div className="trapezoid red-trapezoid">
						<Link to="/games/new">Create a New Game</Link>
					</div>
				</div>
				<h2 className="headerbar hb-dark has-topper" ref={runningHb.ref}>
					Games I'm Running
				</h2>
				{running.length > 0 ? (
					<ul
						className={styles["game-list"]}
						style={{ marginInline: runningHb.margin }}
					>
						{running.map((game) => (
							<GameRow
								key={game.id}
								game={game}
								favorited={favoriteOverrides[game.id] ?? game.favorited}
								onToggleFavorite={() => favoriteMutation.mutate(game.id)}
								pending={
									favoriteMutation.isPending && favoriteMutation.variables === game.id
								}
								showOpenBadge
							/>
						))}
					</ul>
				) : (
					<div className={styles.notice} style={{ marginInline: runningHb.margin }}>
						It seems you aren't running any games yet.
						<br />
						You might want to <Link to="/games/new">get started</Link>.
					</div>
				)}
			</div>

			{retired.length > 0 && (
				<details className={styles["retired-games"]}>
					<summary>Retired games</summary>
					<ul className={styles["game-list"]}>
						{retired.map((game) => (
							<GameRow
								key={game.id}
								game={game}
								favorited={favoriteOverrides[game.id] ?? game.favorited}
								onToggleFavorite={() => favoriteMutation.mutate(game.id)}
								pending={
									favoriteMutation.isPending && favoriteMutation.variables === game.id
								}
							/>
						))}
					</ul>
				</details>
			)}
		</div>
	);
}

function GameRow({
	game,
	favorited,
	onToggleFavorite,
	pending,
	showOpenBadge = false,
}: {
	game: GameListItem;
	favorited: boolean;
	onToggleFavorite: () => void;
	pending: boolean;
	showOpenBadge?: boolean;
}) {
	return (
		<li>
			<span className={styles["game-title"]}>
				<button
					type="button"
					className={styles.favorite}
					onClick={onToggleFavorite}
					disabled={pending}
					title={favorited ? "Unfavorite" : "Favorite"}
				>
					<img
						src={
							favorited
								? "/images/icons/bookmark_on.png"
								: "/images/icons/bookmark_off.png"
						}
						alt={favorited ? "Unfavorite" : "Favorite"}
					/>
				</button>{" "}
				<Link to="/games/$gameId" params={{ gameId: game.id }}>
					{game.title}
				</Link>
			</span>
			<div className={styles["system-type"]}>{game.system}</div>
			<div className={styles["gm-info"]}>
				<Link to="/user/$userId" params={{ userId: game.gm.id }} className="username">
					{game.gm.username}
				</Link>
			</div>
			{/* {showOpenBadge && game.status === "open" && (
				<span className={styles.badge}>Open</span>
			)} */}
			<Link
				to="/forums/{-$forumId}"
				params={{ forumId: game.forum_id }}
				className={styles["forum-link"]}
			>
				<i className="ra ra-speech-bubble" /> Forum
			</Link>
		</li>
	);
}
