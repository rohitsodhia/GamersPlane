import { Link } from "@tanstack/react-router";
import clsx from "clsx";
import { DateTime } from "#/components/DateTime";
import DieIcon from "#/components/DieIcon";
import LockIcon from "#/components/LockIcon";
import PinIcon from "#/components/PinIcon";
import { PAGINATE_PER_PAGE } from "#/lib/config";
import type { Thread, ThreadForum, ThreadOptions } from "#/queries/threads";
import styles from "./-thread-list.module.css";

export function LastPostInfo({
	lastPost,
	forum,
}: {
	lastPost: { datestamp: string; author: { id: number; username: string } } | null;
	// Shown before the author on phones only, where the thread's byline is hidden.
	forum?: { id: number; title: string };
}) {
	if (!lastPost) return <div className={styles["last-post-info"]}>No Posts Yet!</div>;

	return (
		<div className={styles["last-post-info"]}>
			{forum && (
				<Link
					to="/forums/{-$forumId}"
					params={{ forumId: forum.id }}
					className={styles["last-post-forum"]}
				>
					{forum.title}
				</Link>
			)}
			<Link
				to="/user/$userId"
				params={{ userId: lastPost.author.id }}
				className="username"
			>
				{lastPost.author.username}
			</Link>
			<DateTime value={lastPost.datestamp} />
		</div>
	);
}

function ThreadStatusIcon({
	options,
	hasUnread,
}: {
	options: ThreadOptions;
	hasUnread: boolean;
}) {
	const className = clsx("forum-status-icon", !hasUnread && "read");
	const readLabel = hasUnread ? "Unread" : "Read";
	if (options.sticky) {
		return (
			<PinIcon className={className} title={`Thread Status - Sticky, ${readLabel}`} />
		);
	}
	if (options.locked) {
		return (
			<LockIcon className={className} title={`Thread Status - Locked, ${readLabel}`} />
		);
	}
	return <DieIcon className={className} title={`Thread Status - ${readLabel}`} />;
}

function InlineThreadPagination({
	threadId,
	postCount,
}: {
	threadId: number;
	postCount: number;
}) {
	const maxPages = Math.ceil(postCount / PAGINATE_PER_PAGE);
	if (maxPages <= 1) return null;

	const pages = maxPages < 3 ? [1, 2] : [maxPages - 2, maxPages - 1, maxPages];

	return (
		<>
			{pages.map((page) => (
				<Link
					key={page}
					to="/forums/thread/$threadId"
					params={{ threadId }}
					search={{ page }}
				>
					{page}
				</Link>
			))}
		</>
	);
}

function ThreadRow({ thread }: { thread: Thread & { forum?: ThreadForum } }) {
	return (
		<div>
			<ThreadStatusIcon options={thread.options} hasUnread={thread.has_unread} />
			<div className={styles["thread-info"]}>
				{/* Keep the grid cell when read, so the title stays in its column. */}
				{thread.has_unread ? (
					<Link
						to="/forums/thread/$threadId"
						params={{ threadId: thread.id }}
						search={{ view: "new-post" }}
						className="thread-title"
					>
						<img src="/images/icons/new-post.svg" alt="New Post" />
					</Link>
				) : (
					<div></div>
				)}
				<Link
					to="/forums/thread/$threadId"
					params={{ threadId: thread.id }}
					className="thread-title"
				>
					{thread.first_post.title}
				</Link>
				<div className={styles["latest-posts"]}>
					<InlineThreadPagination threadId={thread.id} postCount={thread.post_count} />
					<Link
						to="/forums/thread/$threadId"
						params={{ threadId: thread.id }}
						search={{
							page: Math.max(1, Math.ceil(thread.post_count / PAGINATE_PER_PAGE)),
						}}
						hash={`post-${thread.last_post.id}`}
						className="thread-title"
					>
						<img src="/images/icons/down-arrow.svg" alt="Last Post" />
					</Link>
				</div>
				<div></div>
				<div className={styles["thread-author"]}>
					by{" "}
					<Link
						to="/user/$userId"
						params={{ userId: thread.first_post.author.id }}
						className="username"
					>
						{thread.first_post.author.username}
					</Link>{" "}
					{thread.forum && (
						<>
							in{" "}
							<Link to="/forums/{-$forumId}" params={{ forumId: thread.forum.id }}>
								{thread.forum.title}
							</Link>{" "}
						</>
					)}
					on <DateTime value={thread.first_post.datestamp} />
				</div>
			</div>
			<div>{thread.post_count}</div>
			<LastPostInfo lastPost={thread.last_post} forum={thread.forum} />
		</div>
	);
}

/**
 * The thread grid: column titles plus rows. The caller measures the margin of the
 * header (`headerRef`) and applies it to the rest of the page; `margin` insets the
 * rows to match.
 */
export function ThreadList({
	threads,
	headerRef,
	margin,
}: {
	threads: (Thread & { forum?: ThreadForum })[];
	headerRef: React.Ref<HTMLDivElement>;
	margin: number;
}) {
	return (
		<>
			<div
				className={`headerbar hb-dark listed-items-header ${styles["column-titles"]}`}
				ref={headerRef}
			>
				<div></div>
				<div className={styles["thread-info"]}>Thread</div>
				<div># of Posts</div>
				<div>Last Post</div>
			</div>
			<div className={styles["thread-list"]} style={{ marginInline: margin }}>
				{threads.map((thread) => (
					<ThreadRow key={thread.id} thread={thread} />
				))}
				{threads.length === 0 && <div className={styles["no-threads"]}>No threads</div>}
			</div>
		</>
	);
}
