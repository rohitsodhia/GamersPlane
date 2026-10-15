import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import clsx from "clsx";
import type { ReactNode } from "react";
import { DateTime } from "#/components/DateTime";
import DieIcon from "#/components/DieIcon";
import LoadingSpinner from "#/components/LoadingSpinner";
import { useHbMargined } from "#/lib/use-hb-margined";
import type { GameListItem } from "#/queries/game";
import { latestGamesQueryOptions } from "#/queries/game";
import {
	type RecentScope,
	recentThreadsQueryOptions,
	type Thread,
	type ThreadForum,
	threadsQueryOptions,
} from "#/queries/threads";
import styles from "./-home.module.css";
import { playersLabel } from "./-home-helpers";

export const TAVERN_FORUM_ID = 10;

export function Widget({
	title,
	tone = "dark",
	children,
	footer,
	className,
}: {
	// A link or plain text for the header bar.
	title: ReactNode;
	tone?: "dark" | "orange" | "red";
	children: ReactNode;
	footer?: ReactNode;
	className?: string;
}) {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<section className={clsx(styles["widget"], className)}>
			<h2
				className={clsx("headerbar", styles["widget-header"], styles[`tone-${tone}`])}
				ref={hbMargined.ref}
			>
				{title}
			</h2>
			<div style={{ marginInline: hbMargined.margin }}>
				{children}
				{footer && <div className={styles["widget-footer"]}>{footer}</div>}
			</div>
		</section>
	);
}

export function WidgetError({ children }: { children: ReactNode }) {
	return <div className="banner error-banner">{children}</div>;
}

function ThreadRow({ thread }: { thread: Thread & { forum?: ThreadForum } }) {
	const { last_post: lastPost, forum } = thread;

	return (
		<li className={styles["thread-row"]}>
			<DieIcon
				className={clsx(!thread.has_unread && "read")}
				title={`Thread Status - ${thread.has_unread ? "Unread" : "Read"}`}
			/>
			<div className={styles["thread-info"]}>
				<Link
					to="/forums/thread/$threadId"
					params={{ threadId: thread.id }}
					// Same as the forum listings: unread threads open at the first new post.
					search={thread.has_unread ? { view: "new-post" } : undefined}
					className={styles["thread-title"]}
				>
					{thread.first_post.title}
				</Link>
				<div className={styles["thread-meta"]}>
					by{" "}
					<Link
						to="/user/$userId"
						params={{ userId: lastPost.author.id }}
						className="username"
					>
						{lastPost.author.username}
					</Link>
					, <DateTime value={lastPost.datestamp} />
				</div>
				{forum && (
					<div className={styles["thread-meta"]}>
						in{" "}
						<Link to="/forums/{-$forumId}" params={{ forumId: forum.id }}>
							{forum.title}
						</Link>
					</div>
				)}
			</div>
		</li>
	);
}

export function ThreadRows({
	threads,
}: {
	threads: (Thread & { forum?: ThreadForum })[];
}) {
	return (
		<ul className={styles["thread-list"]}>
			{threads.map((thread) => (
				<ThreadRow key={thread.id} thread={thread} />
			))}
		</ul>
	);
}

export function RecentWidget({
	title,
	scope,
	limit,
	footerLabel,
	tone = "orange",
	className,
}: {
	title: string;
	scope: RecentScope;
	limit: number;
	footerLabel: string;
	tone?: "orange" | "red";
	className?: string;
}) {
	const { data, isPending, isError } = useQuery(
		recentThreadsQueryOptions(scope, 1, limit),
	);

	return (
		<Widget
			title={title}
			tone={tone}
			className={className}
			footer={
				<Link to="/forums/recent" search={{ scope }}>
					{footerLabel}
				</Link>
			}
		>
			{isPending ? (
				<LoadingSpinner />
			) : isError ? (
				<WidgetError>Could not load threads. Please try again.</WidgetError>
			) : data.threads.length === 0 ? (
				<p className={styles["empty"]}>No recent posts.</p>
			) : (
				<ThreadRows threads={data.threads} />
			)}
		</Widget>
	);
}

// Shown in place of the Latest Game Posts widget when the user has no active games.
export function FindGameWidget({ className }: { className?: string }) {
	const { data, isPending, isError } = useQuery(threadsQueryOptions(TAVERN_FORUM_ID));

	return (
		<div className={className}>
			<Widget title="Find a game" tone="red">
				<p className={styles["empty"]}>You're not in any active games.</p>
				<p className={styles["join-game"]}>
					<Link
						to="/forums/{-$forumId}"
						params={{ forumId: TAVERN_FORUM_ID }}
						className="skew-btn"
					>
						Join a game!
					</Link>
				</p>
			</Widget>
			<Widget
				title={
					<Link to="/forums/{-$forumId}" params={{ forumId: TAVERN_FORUM_ID }}>
						Games Tavern
					</Link>
				}
				tone="orange"
			>
				{isPending ? (
					<LoadingSpinner />
				) : isError ? (
					<WidgetError>Could not load the Games Tavern. Please try again.</WidgetError>
				) : (
					<ThreadRows threads={data.threads.slice(0, 3)} />
				)}
			</Widget>
		</div>
	);
}

function LatestGameRow({ game }: { game: GameListItem }) {
	return (
		<li className={styles["latest-game"]}>
			<div className={styles["latest-game-title"]}>
				<Link to="/games/$gameId" params={{ gameId: game.id }}>
					{game.title}
				</Link>{" "}
				({playersLabel(game)})
			</div>
			<div>
				<span className={styles["system"]}>{game.system}</span> run by{" "}
				<Link to="/user/$userId" params={{ userId: game.gm.id }} className="username">
					{game.gm.username}
				</Link>
			</div>
		</li>
	);
}

export function LatestGamesWidget() {
	const { data, isPending, isError } = useQuery(
		latestGamesQueryOptions(null, { excludeMine: true }),
	);

	return (
		<Widget title={<Link to="/games/list">Latest Games</Link>} tone="orange">
			{isPending ? (
				<LoadingSpinner />
			) : isError ? (
				<WidgetError>Could not load games. Please try again.</WidgetError>
			) : data.length === 0 ? (
				<p className={styles["empty"]}>No new games to join.</p>
			) : (
				<ul className={styles["latest-games"]}>
					{data.map((game) => (
						<LatestGameRow key={game.id} game={game} />
					))}
				</ul>
			)}
		</Widget>
	);
}
