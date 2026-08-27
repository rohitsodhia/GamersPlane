import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import { browseGamesQueryOptions, type GameListItem } from "#/queries/game";
import { GameRow } from "./-game-row";
import gameRowStyles from "./-game-row.module.css";
import styles from "./list.module.css";

export const Route = createFileRoute("/games/list/")({
	loaderDeps: ({ search }) => ({
		page: search.page ?? 1,
		search: search.search ?? "",
		systems: search.systems ?? [],
	}),
	loader: ({ context, deps }) =>
		context.queryClient.ensureQueryData(browseGamesQueryOptions(deps)),
	pendingComponent: () => <LoadingSpinner />,
	component: RouteComponent,
});

function RouteComponent() {
	const { page: urlPage, search: urlSearch, systems: urlSystems } = Route.useSearch();
	const page = urlPage ?? 1;

	const {
		data: { games, count },
	} = useSuspenseQuery(
		browseGamesQueryOptions({ search: urlSearch, systems: urlSystems, page }),
	);

	return (
		<>
			{games.length > 0 ? (
				<ul id="games-list" className={gameRowStyles["game-list"]}>
					{games.map((game) => (
						<GameRow key={game.id} game={game} end={<GameTags game={game} />} />
					))}
				</ul>
			) : (
				<div id="no-results" className={gameRowStyles.notice}>
					Doesn't seem like any games are available at this time.
					<br />
					Maybe you should <Link to="/games/new">make one</Link>?
				</div>
			)}

			<div className={styles["games-pagination"]}>
				<Paginate numItems={count} current={page} onPageChange={() => {}} />
			</div>
		</>
	);
}

function GameTags({ game }: { game: GameListItem }) {
	return (
		<div className={styles["game-tags"]}>
			<span
				className={`badge ${game.status === "open" ? "badge-game-open" : "badge-game-closed"}`}
			>
				{game.status === "open" ? "Open" : "Closed"}
			</span>
			{game.public ? (
				<Link
					to="/forums/{-$forumId}"
					params={{ forumId: game.forum_id }}
					className="badge badge-game-public"
				>
					public
				</Link>
			) : (
				<span className="badge badge-game-private">private</span>
			)}
			<span
				className={`badge ${game.player_count < game.num_players ? "badge-game-has-room" : "badge-game-is-full"}`}
			>
				{game.player_count}/{game.num_players}
			</span>
		</div>
	);
}
