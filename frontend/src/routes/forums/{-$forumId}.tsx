import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import DieIcon from "#/components/DieIcon";
import RAIcon from "#/components/RAIcon";
import { useHbMargined } from "#/lib/use-hb-margined";
import { useResizeObserver } from "#/lib/use-resize-observer";
import { type ChildForum, type Forum, forumQueryOptions } from "#/queries/forums";
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
		context.queryClient.ensureQueryData(forumQueryOptions(params.forumId)),
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
				<div>Forum</div>
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
			<div>{forum.post_count}</div>
		</div>
	);
}

function RouteComponent() {
	const loggedIn = useAuthStore((state) => !!state.token);

	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));

	const rootForum = getRootForum(forum);

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();

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
						<a href="/community_guidelines/">community guidelines</a>.
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
