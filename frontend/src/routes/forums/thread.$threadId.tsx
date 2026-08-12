import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import Paginate from "#/components/Paginate";
import { TiptapContent } from "#/components/TiptapContent";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { forumBreadcrumbsQueryOptions } from "#/queries/forums";
import { meFullQueryOptions, type PostSide } from "#/queries/me";
import { type Post, postsQueryOptions } from "#/queries/posts";
import { threadQueryOptions } from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import { Breadcrumbs } from "./-breadcrumbs";

export const Route = createFileRoute("/forums/thread/$threadId")({
	params: {
		parse: (params) => ({ threadId: Number(params.threadId) }),
	},
	validateSearch: z.object({
		view: z.enum(["new-post", "last-post"]).optional(),
		page: z.number().optional(),
	}),
	beforeLoad: ({ params }) => {
		if (!Number.isInteger(params.threadId) || params.threadId < 0) throw notFound();
	},
	loaderDeps: ({ search }) => ({ page: search.page ?? 1 }),
	loader: async ({ context, params, deps }) => {
		const thread = await context.queryClient.ensureQueryData(
			threadQueryOptions(params.threadId),
		);

		await Promise.all([
			context.queryClient.ensureQueryData(
				forumBreadcrumbsQueryOptions(thread.forum_id),
			),
			context.queryClient.ensureQueryData(
				postsQueryOptions(params.threadId, deps.page),
			),
		]);
	},
	component: RouteComponent,
});

function getPostSideClass(postSide: PostSide, index: number) {
	const side = postSide === "c" ? (index % 2 === 0 ? "l" : "r") : postSide;
	return `post-side-${side}`;
}

function PostItem({
	post,
	sideClass,
	threadId,
}: {
	post: Post;
	sideClass: string;
	threadId: number;
}) {
	return (
		<div className={`thread-post ${sideClass}`}>
			<div className="thread-post-author">
				<img src={post.author.avatar} alt={post.author.username} />
				<Link
					to="/user/$id"
					params={{ id: String(post.author.id) }}
					className="username"
				>
					{post.author.username}
				</Link>
			</div>
			<div className="thread-post-body">
				<div className="thread-post-header">
					<span>{post.title}</span>
					<span>{formatDateTime(post.datestamp)}</span>
				</div>
				<TiptapContent content={post.body} className="thread-post-content" />
				<div className="thread-post-actions">
					<button type="button" className="quote-post" disabled title="Coming soon">
						Quote
					</button>
					<Link
						to="/forums/thread/$threadId"
						params={{ threadId }}
						className="edit-post"
						disabled
						title="Coming soon"
					>
						Edit
					</Link>
					<button type="button" className="delete-post" disabled title="Coming soon">
						Delete
					</button>
				</div>
			</div>
		</div>
	);
}

function RouteComponent() {
	const { threadId } = Route.useParams();
	const { page: searchPage } = Route.useSearch();
	const { data: thread } = useSuspenseQuery(threadQueryOptions(threadId));
	const { data: breadcrumbs } = useSuspenseQuery(
		forumBreadcrumbsQueryOptions(thread.forum_id),
	);
	const [page, setPage] = useState(searchPage ?? 1);
	const {
		data: { posts, count },
	} = useSuspenseQuery(postsQueryOptions(threadId, page));

	const loggedIn = useAuthStore((state) => !!state.token);
	const { data: me } = useQuery({ ...meFullQueryOptions, enabled: loggedIn });
	const postSide: PostSide = me?.postSide ?? "r";

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();

	return (
		<div id="thread-page">
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				{thread.title}
			</h1>

			<div style={{ marginInline: hbMarginedHeader.margin }}>
				<Breadcrumbs forum={breadcrumbs} />
			</div>

			<div className="thread-pagination">
				<Paginate numItems={count} current={page} onPageChange={setPage} />
			</div>

			<div id="thread-posts">
				{posts.map((post, index) => (
					<PostItem
						key={post.id}
						post={post}
						sideClass={getPostSideClass(postSide, index)}
						threadId={threadId}
					/>
				))}
			</div>

			<div className="thread-pagination">
				<Paginate numItems={count} current={page} onPageChange={setPage} />
			</div>
		</div>
	);
}
