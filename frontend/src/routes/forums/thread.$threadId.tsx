import { useForm } from "@tanstack/react-form";
import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import { useRef, useState } from "react";
import { z } from "zod";
import ChatPoint from "#/components/ChatPoint";
import Editor, {
	emptyContent,
	isContentEmpty,
	trimTrailingEmptyParagraph,
} from "#/components/Editor";
import Paginate from "#/components/Paginate";
import { TiptapContent } from "#/components/TiptapContent";
import { ApiError } from "#/lib/api";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { forumBreadcrumbsQueryOptions } from "#/queries/forums";
import { meFullQueryOptions, type PostSide } from "#/queries/me";
import { createPost, type Post, postsQueryOptions } from "#/queries/posts";
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
	return side === "l" ? "post-left" : "post-right";
}

function PostItem({
	post,
	sideClass,
	threadId,
	onQuote,
}: {
	post: Post;
	sideClass: string;
	threadId: number;
	onQuote: (post: Post) => void;
}) {
	return (
		<div id={`post-${post.id}`} className={`post ${sideClass}`}>
			<div className="post-author">
				<Link
					to="/user/$id"
					params={{ id: String(post.author.id) }}
					className="username"
				>
					<img
						src={post.author.avatar}
						alt={post.author.username}
						className="user-avatar"
					/>
				</Link>
				<Link
					to="/user/$id"
					params={{ id: String(post.author.id) }}
					className="username"
				>
					{post.author.username}
				</Link>
			</div>
			<div className="post-content">
				<ChatPoint />
				<div className="post-bubble">
					<div className="post-header">
						<span className="post-title">{post.title}</span>
						<span className="post-datestamp">{formatDateTime(post.datestamp)}</span>
					</div>
					<TiptapContent content={post.body} className="post-body" />
				</div>
				<div className="post-actions">
					<button type="button" className="quote-post" onClick={() => onQuote(post)}>
						Quote
					</button>
					<Link
						to="/forums/edit-post/$postId"
						params={{ postId: post.id }}
						className="edit-post"
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
	const queryClient = useQueryClient();

	const loggedIn = useAuthStore((state) => !!state.token);
	const { data: me } = useQuery({ ...meFullQueryOptions, enabled: loggedIn });
	const postSide: PostSide = me?.postSide ?? "r";

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();
	const hbMarginedReply = useHbMargined<HTMLHeadingElement>();

	const [replyErrors, setReplyErrors] = useState<string[]>([]);

	const replyMutation = useMutation({
		mutationFn: createPost,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["posts", threadId] });
		},
	});

	const quickReplyRef = useRef<HTMLFormElement>(null);

	const replyTitle = thread.title.startsWith("Re: ")
		? thread.title
		: `Re: ${thread.title}`;
	const replyForm = useForm({
		defaultValues: {
			body: emptyContent,
		},
		onSubmit: async ({ value, formApi }) => {
			setReplyErrors([]);
			try {
				await replyMutation.mutateAsync({
					thread_id: threadId,
					title: replyTitle,
					body: value.body,
				});
				formApi.reset();
			} catch (exception) {
				if (exception instanceof ApiError) {
					setReplyErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	const handleQuote = (post: Post) => {
		const quotedBody = trimTrailingEmptyParagraph(post.body);
		const quoteNode: JSONContent = {
			type: "quote",
			attrs: { quotee: post.author.username },
			content:
				quotedBody.content && quotedBody.content.length > 0
					? quotedBody.content
					: [{ type: "paragraph" }],
		};

		replyForm.setFieldValue("body", (current) => {
			const base = isContentEmpty(current) ? emptyContent : current;
			// Always follow the quote with a real (not just tiptap's implicit
			// trailing-node) empty paragraph so there's a normal text position
			// to place the cursor at, outside the quote's isolating boundary.
			return {
				...base,
				content: [...(base.content ?? []), quoteNode, { type: "paragraph" }],
			};
		});

		quickReplyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
	};

	return (
		<div id="thread-page">
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				{thread.title}
			</h1>

			<div style={{ marginInline: hbMarginedHeader.margin }}>
				<Breadcrumbs forum={breadcrumbs} />
				<div>
					Be sure to read and follow the{" "}
					<Link to="/community_guidelines">community guidelines</Link>.
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
							onQuote={handleQuote}
						/>
					))}
				</div>

				<div className="thread-pagination">
					<Paginate numItems={count} current={page} onPageChange={setPage} />
				</div>
			</div>

			<h2 className="headerbar hb-dark" ref={hbMarginedReply.ref}>
				Quick Reply
			</h2>
			<form
				id="quick-reply-form"
				ref={quickReplyRef}
				style={{ marginInline: hbMarginedReply.margin }}
				onSubmit={(e) => {
					e.preventDefault();
					replyForm.handleSubmit();
				}}
			>
				{replyErrors.length > 0 && (
					<div className="banner error-banner">
						<ul>
							{replyErrors.map((error) => (
								<li key={error}>{error}</li>
							))}
						</ul>
					</div>
				)}

				<replyForm.Field
					name="body"
					validators={{
						onBlur: ({ value }) =>
							isContentEmpty(value) ? "Message required!" : undefined,
					}}
				>
					{(field) => (
						<Editor
							id={field.name}
							value={field.state.value}
							onBlur={field.handleBlur}
							onChange={(value) => field.handleChange(value)}
							className={field.state.meta.isValid ? "" : "field-invalid"}
						/>
					)}
				</replyForm.Field>

				<replyForm.Subscribe selector={(state) => state.canSubmit}>
					{(canSubmit) => (
						<div className="align-center">
							<button
								type="submit"
								disabled={!canSubmit || replyMutation.isPending}
								className="skew-btn"
							>
								Post
							</button>
						</div>
					)}
				</replyForm.Subscribe>
			</form>
		</div>
	);
}
