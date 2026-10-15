import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import { z } from "zod";
import DieIcon from "#/components/DieIcon";
import ForumSearchForm from "#/components/ForumSearchForm";
import Paginate from "#/components/Paginate";
import RAIcon from "#/components/RAIcon";
import { useHbMargined } from "#/lib/use-hb-margined";
import { useResizeObserver } from "#/lib/use-resize-observer";
import {
	type ChildForum,
	type Forum,
	forumQueryOptions,
	markForumRead,
} from "#/queries/forums";
import { threadsQueryOptions } from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import { useGameBarGame } from "#/stores/game-bar";
import { Breadcrumbs } from "./-breadcrumbs";
import { LastPostInfo, ThreadList } from "./-thread-list";
import styles from "./{-$forumId}.module.css";

export const Route = createFileRoute("/forums/{-$forumId}")({
	params: {
		parse: (params) => ({ forumId: Number(params.forumId ?? 0) }),
		// Forum 0 is the forums index, at /forums.
		stringify: ({ forumId }) => ({ forumId: forumId ? String(forumId) : undefined }),
	},
	validateSearch: z.object({
		page: z.number().optional(),
	}),
	beforeLoad: ({ params }) => {
		if (Number.isNaN(params.forumId)) throw notFound();
	},
	loaderDeps: ({ search }) => ({ page: search.page ?? 1 }),
	loader: async ({ context, params, deps }) => {
		const forum = await context.queryClient
			.ensureQueryData(forumQueryOptions(params.forumId))
			.catch(() => {
				throw notFound();
			});
		if (hasThreads(forum)) {
			await context.queryClient.ensureQueryData(
				threadsQueryOptions(params.forumId, deps.page),
			);
		}
	},
	component: RouteComponent,
});

// The root forum only holds subforums, and a forum the user can't read is only
// shown as a heading over the subforums they can.
const hasThreads = (forum: Forum) =>
	forum.id !== 0 && forum.permissions.includes("forum_read");

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
		<div className={styles["forum-category"]}>
			<div style={{ marginLeft: hbMargined.margin }}>
				<h2 className="trapezoid red-trapezoid">{title}</h2>
			</div>
			<div
				className={`headerbar hb-dark listed-items-header ${styles["column-titles"]}`}
				ref={(el) => {
					hbMargined.ref.current = el;
					heightRef.current = el;
				}}
				style={
					height ? ({ "--hb-height": `${height}px` } as React.CSSProperties) : undefined
				}
			>
				<div></div>
				<div className={styles["forum-info"]}>Forum</div>
				<div># of Threads</div>
				<div># of Posts</div>
				<div>Last Post</div>
			</div>
			<div
				className={styles["category-forums"]}
				style={{ marginInline: hbMargined.margin }}
			>
				{forums.map((childForum) => (
					<CategoryForum key={childForum.id} forum={childForum}></CategoryForum>
				))}
			</div>
		</div>
	);
}

function CategoryForum({ forum }: { forum: ChildForum }) {
	return (
		<div className={styles["forum-category-forum"]}>
			<DieIcon
				className={clsx("forum-status-icon", !forum.has_unread && "read")}
				title={forum.has_unread ? "Forum Status - Unread" : "Forum Status - Read"}
			/>
			<div className={styles["forum-info"]}>
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

function ForumThreads({
	forumId,
	canCreateThread,
}: {
	forumId: number;
	canCreateThread: boolean;
}) {
	const { page: searchPage } = Route.useSearch();
	const [page, setPage] = useState(searchPage ?? 1);
	const {
		data: { threads, count },
	} = useSuspenseQuery(threadsQueryOptions(forumId, page));

	const hbMarginedThreadHeader = useHbMargined<HTMLDivElement>();

	return (
		<div className={styles["forum-threads"]}>
			<div
				className={styles["forum-threads-header"]}
				style={{ marginLeft: hbMarginedThreadHeader.margin }}
			>
				{canCreateThread && (
					<Link
						to="/forums/new-thread/$forumId"
						params={{ forumId }}
						className="skew-btn"
					>
						New Thread
					</Link>
				)}

				<div
					className={styles["thread-pagination"]}
					style={{ marginInline: hbMarginedThreadHeader.margin }}
				>
					<Paginate numItems={count} current={page} onPageChange={setPage} />
				</div>
			</div>
			<ThreadList
				threads={threads}
				headerRef={hbMarginedThreadHeader.ref}
				margin={hbMarginedThreadHeader.margin}
			/>
			<div
				className="thread-pagination"
				style={{ marginInline: hbMarginedThreadHeader.margin }}
			>
				<Paginate numItems={count} current={page} onPageChange={setPage} />
			</div>
		</div>
	);
}

function RouteComponent() {
	const loggedIn = useAuthStore((state) => !!state.token);

	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	useGameBarGame(forum.game_id);
	const queryClient = useQueryClient();
	const markReadMutation = useMutation({
		mutationFn: () => markForumRead(forumId),
		onSuccess: () =>
			Promise.all([
				queryClient.invalidateQueries({ queryKey: ["forums"] }),
				queryClient.invalidateQueries({ queryKey: ["threads"] }),
			]),
	});

	const rootForum = getRootForum(forum);

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();

	const categories = forum.children.filter((child) => child.forum_type === "c");
	const uncategorizedForums = forum.children.filter(
		(child) => child.forum_type !== "c",
	);

	const subscribed: boolean = false;

	return (
		<div className={styles["forum-page"]}>
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				{" "}
				<ForumIcon forumId={forumId} rootForum={rootForum}></ForumIcon>
				{forum.id ? forum.title : "Forums"}
			</h1>

			<div id="forums_top-nav" style={{ marginInline: hbMarginedHeader.margin }}>
				<Breadcrumbs forum={forum} />

				<div className={styles["forums-top-nav-links"]}>
					<div>
						Be sure to read and follow the{" "}
						<Link to="/community-guidelines">community guidelines</Link>.
						{(forum.game_id != null || forum.id === 0) && (
							<ForumSearchForm
								gameId={forum.game_id ?? undefined}
								placeholder={
									forum.game_id != null
										? "Search this game's forums"
										: "Search all forums"
								}
								className={styles["game-search"]}
							/>
						)}
					</div>
					<div>
						{forum.id === 0 && (
							<>
								<div>
									<Link to="/forums/recent" search={{ scope: "latest" }}>
										Latest Posts
									</Link>
									{loggedIn && (
										<>
											/
											<Link to="/forums/recent" search={{ scope: "unread" }}>
												Unread Posts
											</Link>
										</>
									)}
								</div>
								<div>
									<Link to="/forums/recent" search={{ scope: "latest_game" }}>
										Latest Game Posts
									</Link>
								</div>
								<div>
									<Link to="/forums/recent" search={{ scope: "latest_public" }}>
										Latest in Public Games
									</Link>
								</div>
							</>
						)}
						{forum.permissions.includes("forum_moderate") && (
							<div>
								<Link to="/acp/forums/$forumId" params={{ forumId: forum.id }}>
									Administrative Control Panel
								</Link>
							</div>
						)}
					</div>
				</div>
			</div>

			{categories.map((child) => (
				<CategoryGroup key={child.id} title={child.title} forums={child.children} />
			))}
			{uncategorizedForums.length > 0 && (
				<CategoryGroup title="Subforums" forums={uncategorizedForums} />
			)}

			{hasThreads(forum) && (
				<ForumThreads
					forumId={forumId}
					canCreateThread={forum.permissions.includes("forum_create_thread")}
				/>
			)}

			<div
				className={styles["forums-bottom-nav"]}
				style={{ marginInline: hbMarginedHeader.margin }}
			>
				{loggedIn && (
					<p>
						<button
							type="button"
							className="link-btn"
							disabled={markReadMutation.isPending}
							onClick={() => markReadMutation.mutate()}
						>
							{forum.id === 0 ? "Mark All Forums As Read" : "Mark Forum As Read"}
						</button>
					</p>
				)}
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
