import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import DieIcon from "#/components/DieIcon";
import LockIcon from "#/components/LockIcon";
import Paginate from "#/components/Paginate";
import PinIcon from "#/components/PinIcon";
import RAIcon from "#/components/RAIcon";
import { PAGINATE_PER_PAGE } from "#/lib/config";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { useResizeObserver } from "#/lib/use-resize-observer";
import { type ChildForum, type Forum, forumQueryOptions } from "#/queries/forums";
import {
	type ThreadOptions,
	type Thread as ThreadType,
	threadsQueryOptions,
} from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import { Breadcrumbs } from "./-breadcrumbs";

export const Route = createFileRoute("/forums/{-$forumId}")({
	params: {
		parse: (params) => ({ forumId: Number(params.forumId ?? 0) }),
	},
	beforeLoad: ({ params }) => {
		if (Number.isNaN(params.forumId)) throw notFound();
	},
	loader: ({ context, params }) =>
		Promise.all([
			context.queryClient.ensureQueryData(forumQueryOptions(params.forumId)),
			context.queryClient.ensureQueryData(threadsQueryOptions(params.forumId)),
		]),
	component: RouteComponent,
});

const getRootForum = (forum: Forum) => forum.heritage[0]?.id ?? forum.id;

function ForumIcon({ forumId, rootForum }: { forumId: number; rootForum: number }) {
	return (
		<RAIcon
			className={`forum-icon forum-root-${rootForum} forum-id-${forumId}`}
		></RAIcon>
	);
}

function CategoryGroup({ title, forums }: { title: string; forums: ChildForum[] }) {
	const hbMargined = useHbMargined<HTMLDivElement>();

	const [height, setHeight] = useState(0);
	const heightRef = useResizeObserver<HTMLDivElement>((el) =>
		setHeight(el.offsetHeight),
	);

	return (
		<div className="forum-category">
			<div style={{ marginLeft: hbMargined.margin }}>
				<h2 className="trapezoid red-trapezoid">{title}</h2>
			</div>
			<div
				className="headerbar hb-dark column-titles"
				ref={(el) => {
					hbMargined.ref.current = el;
					heightRef.current = el;
				}}
				style={
					height ? ({ "--hb-height": `${height}px` } as React.CSSProperties) : undefined
				}
			>
				<div></div>
				<div className="forum-info">Forum</div>
				<div># of Threads</div>
				<div># of Posts</div>
				<div>Last Post</div>
			</div>
			<div className="category-forums" style={{ marginInline: hbMargined.margin }}>
				{forums.map((childForum) => (
					<CategoryForum key={childForum.id} forum={childForum}></CategoryForum>
				))}
			</div>
		</div>
	);
}

function CategoryForum({ forum }: { forum: ChildForum }) {
	return (
		<div className="forum-category-forum">
			<DieIcon className="forum-status-icon" title="Forum Status - Unread" />
			<div className="forum-info read">
				<Link
					to="/forums/{-$forumId}"
					params={{ forumId: forum.id }}
					className="forum-title"
				>
					{forum.title}
				</Link>
				<div className="forum-description">{forum.description}</div>
			</div>
			<div>{forum.thread_count}</div>
			<div>{forum.post_count}</div>
			<LastPostInfo lastPost={forum.last_post} />
		</div>
	);
}

function LastPostInfo({
	lastPost,
}: {
	lastPost: { datestamp: string; author: { id: number; username: string } } | null;
}) {
	if (!lastPost) return <div className="last-post-info">No Posts Yet!</div>;

	return (
		<div className="last-post-info">
			<Link
				to="/user/$id"
				params={{ id: String(lastPost.author.id) }}
				className="username"
			>
				{lastPost.author.username}
			</Link>
			<span>{formatDateTime(lastPost.datestamp)}</span>
		</div>
	);
}

function Thread({ thread }: { thread: ThreadType }) {
	return (
		<div>
			<ThreadStatusIcon options={thread.options} />
			<div className="thread-info">
				<Link
					to="/thread/$threadId?view=new-post"
					params={{ threadId: thread.id }}
					className="thread-title"
				>
					<img src="/images/icons/new-post.svg" alt="New Post" />
				</Link>
				<Link
					to="/thread/$threadId"
					params={{ threadId: thread.id }}
					className="thread-title"
				>
					{thread.first_post.title}
				</Link>
				<div className="latest-posts">
					<InlineThreadPagination threadId={thread.id} postCount={thread.post_count} />
					<Link
						to="/thread/$threadId?view=last-post"
						params={{ threadId: thread.id }}
						className="thread-title"
					>
						<img src="/images/icons/down-arrow.svg" alt="Last Post" />
					</Link>
				</div>
				<div></div>
				<div className="thread-author">
					by{" "}
					<Link
						to="/user/$id"
						params={{ id: String(thread.first_post.author.id) }}
						className="username"
					>
						{thread.first_post.author.username}
					</Link>{" "}
					on <span>{formatDateTime(thread.first_post.datestamp)}</span>
				</div>
			</div>
			<div>{thread.post_count}</div>
			<LastPostInfo lastPost={thread.last_post} />
		</div>
	);
}

function ThreadStatusIcon({ options }: { options: ThreadOptions }) {
	const props = { className: "forum-status-icon" };
	if (options.sticky) {
		return <PinIcon {...props} title="Thread Status - Sticky" />;
	}
	if (options.locked) {
		return <LockIcon {...props} title="Thread Status - Locked" />;
	}
	return <DieIcon {...props} title="Forum Status - Unread" />;
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
				<Link key={page} to={`/thread/$threadId?page=${page}`} params={{ threadId }}>
					{page}
				</Link>
			))}
		</>
	);
}

function RouteComponent() {
	const loggedIn = useAuthStore((state) => !!state.token);

	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	const [page, setPage] = useState(1);
	const {
		data: { threads, count },
	} = useSuspenseQuery(threadsQueryOptions(forumId, page));

	const rootForum = getRootForum(forum);

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();
	const hbMarginedThreadHeader = useHbMargined<HTMLDivElement>();

	const categories = forum.children.filter((child) => child.forum_type === "c");
	const uncategorizedForums = forum.children.filter(
		(child) => child.forum_type !== "c",
	);

	const subscribed: boolean = false;

	return (
		<div id="forum-page">
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				{" "}
				<ForumIcon forumId={forumId} rootForum={rootForum}></ForumIcon>
				{forum.id ? forum.title : "Forums"}
			</h1>

			<div id="forums_top-nav" style={{ marginInline: hbMarginedHeader.margin }}>
				<Breadcrumbs forum={forum} />

				<div id="forums_top-nav-links">
					<div>
						Be sure to read and follow the{" "}
						<Link to="/community_guidelines">community guidelines</Link>.
					</div>
					<div>
						{forum.id === 0 && (
							<>
								<div>
									<a href="/forums/search/?search=latestPosts">Latest Posts</a>/
									<a href="/forums/search/?search=unreadPosts">Unread Posts</a>
								</div>
								<div>
									<a href="/forums/search/?search=latestGamePosts">Latest Game Posts</a>
								</div>
								<div>
									<a href="/forums/search/?search=latestPublicPosts">
										Latest in Public Games
									</a>
								</div>
							</>
						)}
						<div>
							<Link to="/forums/acp/{-$forumId}/" params={{ forumId: forum.id }}>
								Administrative Control Panel
							</Link>
						</div>
					</div>
				</div>
			</div>

			{categories.map((child) => (
				<CategoryGroup key={child.id} title={child.title} forums={child.children} />
			))}
			{uncategorizedForums.length > 0 && (
				<CategoryGroup title="Subforums" forums={uncategorizedForums} />
			)}

			<div id="forum_threads">
				<div
					className="forum-threads-header"
					style={{ marginLeft: hbMarginedThreadHeader.margin }}
				>
					<Link
						to="/forums/new-thread/$forumId"
						params={{ forumId: forum.id }}
						className="skew-btn"
					>
						New Thread
					</Link>

					<div
						className="thread-pagination"
						style={{ marginInline: hbMarginedThreadHeader.margin }}
					>
						<Paginate numItems={count} current={page} onPageChange={setPage} />
					</div>
				</div>
				<div
					className="headerbar hb-dark column-titles"
					ref={hbMarginedThreadHeader.ref}
				>
					<div></div>
					<div className="thread-info">Thread</div>
					<div># of Posts</div>
					<div>Last Post</div>
				</div>
				<div id="thread-list" style={{ marginInline: hbMarginedThreadHeader.margin }}>
					{threads.map((thread) => (
						<Thread key={thread.id} thread={thread} />
					))}
					{threads.length === 0 && <div id="no-threads">No threads</div>}
				</div>
				<div
					className="thread-pagination"
					style={{ marginInline: hbMarginedThreadHeader.margin }}
				>
					<Paginate numItems={count} current={page} onPageChange={setPage} />
				</div>
			</div>

			<div id="forums_bottom-nav" style={{ marginInline: hbMarginedHeader.margin }}>
				<p>
					<a href={`/forums/process/read/${forum.id}`}>Mark Forum As Read</a>
				</p>
				<p>
					<a href={`/forums/process/subscribe/?forumID=${forum.id}`}>
						{subscribed ? "Unsubscribe from" : "Subscribe to"} forum
					</a>
				</p>
				{loggedIn && (
					<p>
						<a href="/forums/subscriptions/">Manage Subscriptions</a>
					</p>
				)}
			</div>
		</div>
	);
}
