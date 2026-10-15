import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import { Button } from "react-aria-components";
import { DateTime } from "#/components/DateTime";
import DieIcon from "#/components/DieIcon";
import LoadingSpinner from "#/components/LoadingSpinner";
import RAIcon from "#/components/RAIcon";
import { TiptapContent } from "#/components/TiptapContent";
import { type MyGameListItem, myGamesQueryOptions } from "#/queries/game";
import { announcementQueryOptions, recentThreadsQueryOptions } from "#/queries/threads";
import styles from "./-home.module.css";
import {
	FindGameWidget,
	LatestGamesWidget,
	RecentWidget,
	TAVERN_FORUM_ID,
	Widget,
	WidgetError,
} from "./-home-widgets";

function AnnouncementWidget() {
	const { data, isPending, isError } = useQuery(announcementQueryOptions());
	// Local only; every visit starts open.
	const [open, setOpen] = useState(true);

	if (isPending) return <div className={styles["announcement-placeholder"]} />;
	if (isError) {
		return (
			<WidgetError>Could not load the announcement. Please try again.</WidgetError>
		);
	}
	return (
		<Widget
			className={styles["announcement"]}
			tone="orange"
			title={
				<span className={styles["announcement-title"]}>
					<Link to="/forums/thread/$threadId" params={{ threadId: data.id }}>
						{data.title}
					</Link>
					<Button
						className={styles["toggle"]}
						onPress={() => setOpen(!open)}
						aria-expanded={open}
						aria-label={open ? "Hide announcement" : "Show announcement"}
					>
						{open ? "▲" : "▼"}
					</Button>
				</span>
			}
		>
			{open && <TiptapContent content={data.post.body} npcs={data.post.content_npcs} />}
		</Widget>
	);
}

function GameRows({ games }: { games: MyGameListItem[] }) {
	return (
		<>
			{games.map((game) => (
				<li key={game.id} className={styles["game-row"]}>
					<DieIcon
						className={clsx(!game.has_unread && "read")}
						title={`Game Status - ${game.has_unread ? "Unread" : "Read"}`}
					/>
					<div className={styles["game-info"]}>
						<Link
							to="/games/$gameId"
							params={{ gameId: game.id }}
							className={styles["game-title"]}
						>
							{game.title}
						</Link>
						<div className={styles["game-meta"]}>
							<Link
								to="/user/$userId"
								params={{ userId: game.gm.id }}
								className="username"
							>
								{game.gm.username}
							</Link>
							{game.last_activity && (
								<>
									{" "}
									<DateTime value={game.last_activity} />
								</>
							)}
						</div>
					</div>
				</li>
			))}
		</>
	);
}

function MyGames() {
	const { data, isPending, isError } = useQuery(myGamesQueryOptions());

	if (isPending) return <LoadingSpinner />;
	if (isError) {
		return <WidgetError>Could not load your games. Please try again.</WidgetError>;
	}

	// Favorited games get their own section; the API order is kept within each.
	const bookmarked = data.filter((game) => game.favorited);
	const rest = data.filter((game) => !game.favorited);

	return (
		<>
			{bookmarked.length > 0 && (
				<Widget title={<Link to="/games">Bookmarked Games</Link>} tone="red">
					<ul className={styles["game-grid"]}>
						<GameRows games={bookmarked} />
					</ul>
				</Widget>
			)}
			<Widget title={<Link to="/games">Your Games</Link>} tone="orange">
				<ul className={styles["game-grid"]}>
					<li className={styles["game-row"]}>
						<RAIcon className="ra-beer" />
						<div className={styles["game-info"]}>
							<Link
								to="/forums/{-$forumId}"
								params={{ forumId: TAVERN_FORUM_ID }}
								className={styles["game-title"]}
							>
								Games Tavern
							</Link>
						</div>
					</li>
					<GameRows games={rest} />
				</ul>
			</Widget>
		</>
	);
}

// Latest Game Posts, or the find-a-game prompt when the user has none.
function GamePostsColumn({ className }: { className?: string }) {
	const { data, isPending } = useQuery(recentThreadsQueryOptions("latest_game", 1, 5));

	// On error the widget itself shows the message, so don't swap it out.
	if (!isPending && data && data.threads.length === 0) {
		return <FindGameWidget className={className} />;
	}
	return (
		<RecentWidget
			className={className}
			title="Latest Game Posts"
			scope="latest_game"
			limit={5}
			footerLabel="All Latest Game Posts"
			tone="red"
		/>
	);
}

function Home() {
	return (
		<div className={styles["home"]}>
			<AnnouncementWidget />
			<div className={styles["columns"]}>
				<div className={styles["col-left"]}>
					<LatestGamesWidget />
					<RecentWidget
						title="Latest in Public Games"
						scope="latest_public"
						limit={2}
						footerLabel="Latest in Public Games"
					/>
				</div>
				<RecentWidget
					className={styles["col-middle"]}
					title="Community Posts"
					scope="latest"
					limit={5}
					footerLabel="All Latest Posts"
				/>
				<GamePostsColumn className={styles["col-right"]} />
			</div>
			<MyGames />
		</div>
	);
}
export default Home;
