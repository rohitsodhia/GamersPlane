import { useForm } from "@tanstack/react-form";
import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import {
	createFileRoute,
	Link,
	notFound,
	redirect,
	useNavigate,
} from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import Editor, {
	emptyContent,
	isContentEmpty,
	trimTrailingEmptyParagraph,
} from "#/components/Editor";
import LockIcon from "#/components/LockIcon";
import Paginate from "#/components/Paginate";
import PinIcon from "#/components/PinIcon";
import { TiptapContent } from "#/components/TiptapContent";
import { ApiError } from "#/lib/api";
import { PAGINATE_PER_PAGE } from "#/lib/config";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { useScrollToHash } from "#/lib/use-scroll-to-hash";
import {
	forumBreadcrumbsQueryOptions,
	forumCharactersQueryOptions,
	forumDecksQueryOptions,
} from "#/queries/forums";
import { meFullQueryOptions, type PostSide } from "#/queries/me";
import { createPost, deletePost, type Post, postsQueryOptions } from "#/queries/posts";
import {
	markThreadUnread,
	recordThreadRead,
	type ThreadOptionsUpdate,
	threadQueryOptions,
	updateThread,
} from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import {
	type Attachments,
	attachmentAccess,
	attachmentErrors,
	buildAttachmentPayload,
	emptyAttachments,
} from "./-attachment-rows";
import { Breadcrumbs } from "./-breadcrumbs";
import ChatPoint from "./-chat-point";
import { canChangePost, canWrite } from "./-permissions";
import { PostAsPicker } from "./-post-as-picker";
import { PostAttachmentsEditor } from "./-post-attachments";
import { PostDrawList } from "./-post-draw-list";
import { PostRollList } from "./-post-roll-list";
import { ThreadPoll } from "./-thread-poll";
import styles from "./thread.$threadId.module.css";

export const Route = createFileRoute("/forums/thread/$threadId")({
	params: {
		parse: (params) => ({ threadId: Number(params.threadId) }),
	},
	validateSearch: z.object({
		view: z.enum(["new-post"]).optional(),
		page: z.number().optional(),
	}),
	beforeLoad: ({ params }) => {
		if (!Number.isInteger(params.threadId) || params.threadId < 0) throw notFound();
	},
	loaderDeps: ({ search }) => ({ page: search.page ?? 1, view: search.view }),
	loader: async ({ context, params, deps }) => {
		const wantsNewPost = deps.view === "new-post";
		// The unread position changes as the user reads, so a jump to the first
		// new post must not use cached details.
		const thread = await (wantsNewPost
			? context.queryClient.fetchQuery({
					...threadQueryOptions(params.threadId),
					staleTime: 0,
				})
			: context.queryClient.ensureQueryData(threadQueryOptions(params.threadId))
		).catch(() => {
			throw notFound();
		});

		if (wantsNewPost) {
			// Drops `view`; with nothing unread this stays on page 1.
			throw redirect({
				to: "/forums/thread/$threadId",
				params: { threadId: params.threadId },
				search: thread.first_unread_page ? { page: thread.first_unread_page } : {},
				hash: thread.first_unread_post_id
					? `post-${thread.first_unread_post_id}`
					: undefined,
				replace: true,
			});
		}

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
	canWrite,
	canEdit,
	canDelete,
	isAuthor,
	canToggleDraws,
	onQuote,
	onDelete,
	onMarkUnread,
}: {
	post: Post;
	sideClass: string;
	threadId: number;
	page: number;
	isFirstPost: boolean;
	// Quoting fills in the reply form, so it needs write.
	canWrite: boolean;
	canEdit: boolean;
	canDelete: boolean;
	// The viewer wrote the post: they see every drawn card.
	isAuthor: boolean;
	// Revealing or hiding cards: not allowed in a locked thread without moderating.
	canToggleDraws: boolean;
	onQuote: (post: Post) => void;
	onDelete: (post: Post) => void;
	// Only passed for the thread's last post.
	onMarkUnread?: () => void;
}) {
	const deleteConfirmId = `delete-post-confirm-${post.id}`;
	const postedAs = post.posted_as;
	return (
		<div id={`post-${post.id}`} className={`${styles.post} ${styles[sideClass] ?? ""}`}>
			<div className={styles["post-author"]}>
				{postedAs?.avatar ? (
					// The character takes the avatar slot; the user's sits on its corner.
					<div className={styles["avatar-stack"]}>
						{postedAs.can_view ? (
							<Link to="/characters/$characterId" params={{ characterId: postedAs.id }}>
								<img
									src={postedAs.avatar}
									alt={postedAs.name}
									className={styles["user-avatar"]}
								/>
							</Link>
						) : (
							<img
								src={postedAs.avatar}
								alt={postedAs.name}
								className={styles["user-avatar"]}
							/>
						)}
						<Link
							to="/user/$userId"
							params={{ userId: post.author.id }}
							className={styles["avatar-corner"]}
						>
							<img src={post.author.avatar} alt={post.author.username} />
						</Link>
					</div>
				) : (
					<Link
						to="/user/$userId"
						params={{ userId: post.author.id }}
						className="username"
					>
						<img
							src={post.author.avatar}
							alt={post.author.username}
							className={styles["user-avatar"]}
						/>
					</Link>
				)}
				{postedAs && (
					<div className={styles["character-name"]}>
						{postedAs.can_view ? (
							<Link to="/characters/$characterId" params={{ characterId: postedAs.id }}>
								{postedAs.name}
							</Link>
						) : (
							postedAs.name
						)}
					</div>
				)}
				<Link
					to="/user/$userId"
					params={{ userId: post.author.id }}
					className={clsx("username", postedAs && styles["author-username"])}
				>
					{post.author.username}
				</Link>
			</div>
			<div className={styles["post-content"]}>
				<ChatPoint className={styles["chat-point"]} />
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
					<PostRollList rolls={post.rolls} />
					<PostDrawList
						postId={post.id}
						threadId={threadId}
						draws={post.draws}
						isAuthor={isAuthor}
						canToggle={canToggleDraws}
					/>
				</div>
				<div className={styles["post-actions"]}>
					{onMarkUnread && (
						<button
							type="button"
							className={styles["mark-unread"]}
							onClick={onMarkUnread}
						>
							Mark as unread
						</button>
					)}
					{canWrite && (
						<button type="button" className="quote-post" onClick={() => onQuote(post)}>
							Quote
						</button>
					)}
					{canEdit && (
						<Link
							to="/forums/edit-post/$postId"
							params={{ postId: post.id }}
							className="edit-post"
							title="Coming soon"
						>
							Edit
						</Link>
					)}
					{canDelete && (
						<button
							type="button"
							className="delete-post"
							popoverTarget={deleteConfirmId}
						>
							Delete
						</button>
					)}
				</div>
			</div>
			{canDelete && (
				// biome-ignore lint/a11y/useKeyWithClickEvents: delegated click handler catches bubbled clicks from interactive <button> children, which already fire click on keyboard activation
				// biome-ignore lint/a11y/noStaticElementInteractions: delegated click handler catches bubbled clicks from interactive <button> children
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
			)}
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
	// The search param can change without a remount (e.g. a redirect or a post
	// link on this same thread), so follow it.
	const [prevSearchPage, setPrevSearchPage] = useState(searchPage);
	if (searchPage !== prevSearchPage) {
		setPrevSearchPage(searchPage);
		setPage(searchPage ?? 1);
	}
	const {
		data: { posts, count },
	} = useSuspenseQuery(postsQueryOptions(threadId, page));
	const queryClient = useQueryClient();
	const navigate = useNavigate();
	useScrollToHash([posts]);

	const loggedIn = useAuthStore((state) => !!state.token);

	const invalidateReadState = () =>
		Promise.all([
			queryClient.invalidateQueries({ queryKey: ["threads"] }),
			queryClient.invalidateQueries({ queryKey: ["forums"] }),
		]);

	// Record what the user has seen, once per (thread, page) view. The ref keeps
	// refetches of the details (e.g. after mark-unread) from firing it again and
	// undoing the change.
	const recordedRef = useRef<string | null>(null);
	const lastPostId = posts.at(-1)?.id;
	const firstUnreadPage = thread.first_unread_page;
	useEffect(() => {
		if (!loggedIn || lastPostId === undefined) return;
		if (firstUnreadPage == null || page < firstUnreadPage) return;
		const key = `${threadId}:${page}`;
		if (recordedRef.current === key) return;
		recordedRef.current = key;
		recordThreadRead(threadId, lastPostId)
			.then(() =>
				Promise.all([
					queryClient.invalidateQueries({ queryKey: ["threads"] }),
					queryClient.invalidateQueries({ queryKey: ["forums"] }),
				]),
			)
			.catch(() => {});
	}, [loggedIn, threadId, page, lastPostId, firstUnreadPage, queryClient]);

	const isLastPage = page >= Math.ceil(count / PAGINATE_PER_PAGE);
	const markUnreadMutation = useMutation({
		mutationFn: () => {
			// The details refetch below must not read as "this page is newly seen".
			recordedRef.current = `${threadId}:${page}`;
			return markThreadUnread(threadId);
		},
		onSuccess: async () => {
			await invalidateReadState();
			navigate({ to: "/forums/{-$forumId}", params: { forumId: thread.forum_id } });
		},
	});

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

	const { data: me } = useQuery({ ...meFullQueryOptions, enabled: loggedIn });
	const postSide: PostSide = me?.postSide ?? "r";

	const isModerator = thread.permissions.includes("forum_moderate");
	const [modError, setModError] = useState<string | null>(null);
	const modMutation = useMutation({
		mutationFn: (options: ThreadOptionsUpdate) => updateThread(threadId, options),
		onMutate: () => setModError(null),
		onSuccess: () =>
			Promise.all([
				// The thread details (locking gates replying and editing) and the lists.
				queryClient.invalidateQueries({ queryKey: ["threads"] }),
				queryClient.invalidateQueries({ queryKey: ["forums"] }),
			]),
		onError: (exception) =>
			setModError(
				exception instanceof ApiError
					? exception.errors.map((e) => e.detail).join(" ")
					: "Couldn't update the thread.",
			),
	});

	const userCanWrite = canWrite(thread);
	const canToggleDraws =
		!thread.options.locked || thread.permissions.includes("forum_moderate");

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();
	const hbMarginedReply = useHbMargined<HTMLHeadingElement>();

	const [replyErrors, setReplyErrors] = useState<string[]>([]);

	const replyMutation = useMutation({
		mutationFn: createPost,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["posts", threadId] });
			queryClient.invalidateQueries({
				queryKey: threadQueryOptions(threadId).queryKey,
			});
			queryClient.invalidateQueries({ queryKey: ["forums"] });
		},
	});

	const quickReplyRef = useRef<HTMLFormElement>(null);

	const [attachments, setAttachments] = useState<Attachments>(emptyAttachments);
	const [attachmentsOpen, setAttachmentsOpen] = useState(false);
	const [showAttachmentErrors, setShowAttachmentErrors] = useState(false);
	const access = attachmentAccess(thread.options, thread.permissions);
	const { data: decksData } = useQuery({
		...forumDecksQueryOptions(thread.forum_id),
		enabled: userCanWrite && access.draws,
	});
	const decks = access.draws ? (decksData ?? []) : [];
	const attachmentRowErrors = attachmentErrors(attachments, access, decks);
	const hasAttachmentUI = access.rolls || (access.draws && decks.length > 0);
	const attachmentCount = attachments.rolls.length + attachments.draws.length;

	// Undefined until the user picks, so the thread's default applies until then.
	// Kept after a post (the form's reset doesn't touch it).
	const { data: charactersData } = useQuery({
		...forumCharactersQueryOptions(thread.forum_id, threadId),
		enabled: userCanWrite,
	});
	const [pickedPostAs, setPickedPostAs] = useState<number | null | undefined>(
		undefined,
	);
	const postAs =
		pickedPostAs === undefined ? (charactersData?.default_id ?? null) : pickedPostAs;

	const replyTitle = thread.title.startsWith("Re: ")
		? thread.title
		: `Re: ${thread.title}`;
	const replyForm = useForm({
		defaultValues: {
			body: emptyContent,
		},
		onSubmit: async ({ value, formApi }) => {
			setReplyErrors([]);
			if (Object.keys(attachmentRowErrors).length > 0) {
				setShowAttachmentErrors(true);
				setAttachmentsOpen(true);
				setReplyErrors(["Fix the problems under Add rolls / draws before posting."]);
				return;
			}
			try {
				await replyMutation.mutateAsync({
					thread_id: threadId,
					title: replyTitle,
					body: value.body,
					posted_as_id: postAs,
					...buildAttachmentPayload(attachments, access),
				});
				formApi.reset();
				setAttachments(emptyAttachments);
				setAttachmentsOpen(false);
				setShowAttachmentErrors(false);
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
				<div className={styles["thread-menu"]}>
					<div>
						<Breadcrumbs forum={breadcrumbs} />
						<div>
							Be sure to read and follow the{" "}
							<Link to="/community-guidelines">community guidelines</Link>.
						</div>
					</div>

					{isModerator && (
						<div className={styles["mod-actions"]}>
							<button
								type="button"
								aria-pressed={thread.options.sticky}
								disabled={modMutation.isPending}
								onClick={() => modMutation.mutate({ sticky: !thread.options.sticky })}
							>
								<PinIcon
									title={thread.options.sticky ? "Unsticky thread" : "Sticky thread"}
								/>
							</button>
							<button
								type="button"
								aria-pressed={thread.options.locked}
								disabled={modMutation.isPending}
								onClick={() => modMutation.mutate({ locked: !thread.options.locked })}
							>
								<LockIcon
									title={thread.options.locked ? "Unlock thread" : "Lock thread"}
								/>
							</button>
						</div>
					)}
				</div>
				{modError && <div className="error">{modError}</div>}

				{thread.poll && (
					<ThreadPoll
						threadId={threadId}
						poll={thread.poll}
						locked={thread.options.locked}
						loggedIn={loggedIn}
					/>
				)}

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
							canWrite={userCanWrite}
							canEdit={canChangePost(thread, post.author.id, me?.id, "forum_edit")}
							canDelete={canChangePost(
								thread,
								post.author.id,
								me?.id,
								post.id === thread.first_post_id
									? "forum_delete_thread"
									: "forum_delete",
							)}
							isAuthor={me !== undefined && post.author.id === me.id}
							canToggleDraws={canToggleDraws}
							onQuote={handleQuote}
							onDelete={(post) => deleteMutation.mutate(post.id)}
							onMarkUnread={
								loggedIn && isLastPage && index === posts.length - 1
									? () => markUnreadMutation.mutate()
									: undefined
							}
						/>
					))}
				</div>

				<div className="thread-pagination">
					<Paginate numItems={count} current={page} onPageChange={setPage} />
				</div>
			</div>

			{userCanWrite && (
				<>
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

						{charactersData && charactersData.characters.length > 0 && (
							<div className={styles["quick-reply-post-as"]}>
								<label htmlFor="quick-reply-post-as">Post as:</label>
								<PostAsPicker
									id="quick-reply-post-as"
									characters={charactersData.characters}
									viewerId={me?.id}
									value={postAs}
									onChange={setPickedPostAs}
								/>
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

						{hasAttachmentUI && (
							<div className={styles["quick-reply-attachments"]}>
								<button
									type="button"
									aria-expanded={attachmentsOpen}
									onClick={() => setAttachmentsOpen((open) => !open)}
								>
									{attachmentsOpen ? "Hide rolls / draws" : "Add rolls / draws"}
									{attachmentCount > 0 && ` (${attachmentCount})`}
								</button>
								{attachmentsOpen && (
									<PostAttachmentsEditor
										value={attachments}
										onChange={setAttachments}
										access={access}
										decks={decks}
										showErrors={showAttachmentErrors}
									/>
								)}
							</div>
						)}

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
				</>
			)}
		</div>
	);
}
