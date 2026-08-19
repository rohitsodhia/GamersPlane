import { useForm } from "@tanstack/react-form";
import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
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
import { useScrollToHash } from "#/lib/use-scroll-to-hash";
import { forumBreadcrumbsQueryOptions } from "#/queries/forums";
import { meFullQueryOptions, type PostSide } from "#/queries/me";
import { createPost, deletePost, type Post, postsQueryOptions } from "#/queries/posts";
import { threadQueryOptions } from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import { Breadcrumbs } from "./-breadcrumbs";
import styles from "./thread.$threadId.module.css";

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
	page,
	isFirstPost,
	onQuote,
	onDelete,
}: {
	post: Post;
	sideClass: string;
	threadId: number;
	page: number;
	isFirstPost: boolean;
	onQuote: (post: Post) => void;
	onDelete: (post: Post) => void;
}) {
	const deleteConfirmId = `delete-post-confirm-${post.id}`;
	return (
		<div id={`post-${post.id}`} className={`${styles.post} ${styles[sideClass] ?? ""}`}>
			<div className={styles["post-author"]}>
				<Link
					to="/user/$userId"
					params={{ userId: String(post.author.id) }}
					className="username"
				>
					<img
						src={post.author.avatar}
						alt={post.author.username}
						className={styles["user-avatar"]}
					/>
				</Link>
				<Link
					to="/user/$userId"
					params={{ userId: String(post.author.id) }}
					className="username"
				>
					{post.author.username}
				</Link>
			</div>
			<div className={styles["post-content"]}>
				<ChatPoint />
				<div className={styles["post-bubble"]}>
					<div className={styles["post-header"]}>
						<Link
							to="/forums/thread/$threadId"
							params={{ threadId }}
							search={{ page }}
							hash={`post-${post.id}`}
							className={styles["post-title"]}
						>
							{post.title}
						</Link>
						<span className={styles["post-datestamp"]}>
							{formatDateTime(post.datestamp)}
						</span>
					</div>
					<TiptapContent content={post.body} className="post-body" />
				</div>
				<div className={styles["post-actions"]}>
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
					<button type="button" className="delete-post" popoverTarget={deleteConfirmId}>
						Delete
					</button>
				</div>
			</div>
			{/* biome-ignore lint/a11y/useKeyWithClickEvents: delegated click handler catches bubbled clicks from interactive <button> children, which already fire click on keyboard activation */}
			{/* biome-ignore lint/a11y/noStaticElementInteractions: delegated click handler catches bubbled clicks from interactive <button> children */}
			<div
				id={deleteConfirmId}
				popover="auto"
				className={styles["confirm-popover"]}
				onClick={(e) => {
					if (e.target instanceof HTMLElement) {
						e.currentTarget.hidePopover();
					}
				}}
			>
				<p>
					{isFirstPost
						? "Are you sure you want to delete this thread? This will delete the entire thread and all of its posts."
						: "Are you sure you want to delete this post?"}
				</p>
				<div className={styles["confirm-popover-actions"]}>
					<button type="button" className="skew-btn" onClick={() => onDelete(post)}>
						Yes
					</button>
					<button type="button">No</button>
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
	const navigate = useNavigate();
	useScrollToHash([posts]);

	const deleteMutation = useMutation({
		mutationFn: deletePost,
		onSuccess: (_data, postId) => {
			if (postId === thread.first_post_id) {
				navigate({ to: "/forums/{-$forumId}", params: { forumId: thread.forum_id } });
			} else {
				queryClient.invalidateQueries({ queryKey: ["posts", threadId] });
			}
		},
	});

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
		<div className={styles["thread-page"]}>
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

				<div className={styles["thread-posts"]}>
					{posts.map((post, index) => (
						<PostItem
							key={post.id}
							post={post}
							sideClass={getPostSideClass(postSide, index)}
							threadId={threadId}
							page={page}
							isFirstPost={post.id === thread.first_post_id}
							onQuote={handleQuote}
							onDelete={(post) => deleteMutation.mutate(post.id)}
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
				className={styles["quick-reply-form"]}
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
