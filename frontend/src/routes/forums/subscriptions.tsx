import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { FadeOut } from "#/components/FadeOut";
import { Select } from "#/components/Select";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useFlash } from "#/lib/use-flash";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	buildSubscriptionTree,
	FORUM_SUB_TYPE_OPTIONS,
	type ForumSubType,
	type SubscriptionTreeNode,
	setForumSubscribed,
	setThreadSubscribed,
	subscriptionErrorMessage,
	subscriptionsQueryOptions,
} from "#/queries/forumSubscriptions";
import { forumQueryOptions } from "#/queries/forums";
import { meFullQueryOptions, refreshMe, updateUserSettings } from "#/queries/me";
import { threadQueryOptions } from "#/queries/threads";
import styles from "./subscriptions.module.css";

export const Route = createFileRoute("/forums/subscriptions")({
	beforeLoad: requireAuth,
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			Promise.all([
				context.queryClient.ensureQueryData(subscriptionsQueryOptions),
				context.queryClient.ensureQueryData(meFullQueryOptions),
			]),
			location,
		),
	component: RouteComponent,
});

type Unsubscribe = { kind: "forum" | "thread"; id: number };

function ForumNode({
	node,
	onUnsubscribe,
	pending,
}: {
	node: SubscriptionTreeNode;
	onUnsubscribe: (target: Unsubscribe) => void;
	pending: boolean;
}) {
	return (
		<li>
			<div className={styles["row"]}>
				{node.subscribed ? (
					<Link
						to="/forums/{-$forumId}"
						params={{ forumId: node.id }}
						className={styles["title"]}
					>
						{node.title}
					</Link>
				) : (
					// An ancestor shown only so its subscribed subforums have a place.
					<span className={`${styles["title"]} ${styles["heading-only"]}`}>
						{node.title}
					</span>
				)}
				{node.subscribed && (
					<button
						type="button"
						className="link-btn"
						disabled={pending}
						aria-label={`Unsubscribe from forum ${node.title}`}
						onClick={() => onUnsubscribe({ kind: "forum", id: node.id })}
					>
						Unsubscribe
					</button>
				)}
			</div>
			{node.children.length > 0 && (
				<ul className={styles["tree"]}>
					{node.children.map((child) => (
						<ForumNode
							key={child.id}
							node={child}
							onUnsubscribe={onUnsubscribe}
							pending={pending}
						/>
					))}
				</ul>
			)}
		</li>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const queryClient = useQueryClient();
	const { data: subscriptions } = useSuspenseQuery(subscriptionsQueryOptions);
	const { data: me } = useSuspenseQuery(meFullQueryOptions);
	const [saved, flashSaved] = useFlash();

	const settingMutation = useMutation({
		mutationFn: (forumSubType: ForumSubType) => updateUserSettings({ forumSubType }),
		onSuccess: async () => {
			await refreshMe(queryClient);
			flashSaved();
		},
	});
	// Show the pick straight away; if the save fails it falls back to the stored one.
	const forumSubType =
		(settingMutation.isPending ? settingMutation.variables : undefined) ??
		me.forumSubType;

	const unsubscribeMutation = useMutation({
		mutationFn: ({ kind, id }: Unsubscribe) =>
			kind === "forum" ? setForumSubscribed(id, false) : setThreadSubscribed(id, false),
		onSuccess: (_data, { kind, id }) =>
			Promise.all([
				queryClient.invalidateQueries({ queryKey: subscriptionsQueryOptions.queryKey }),
				// Keep any cached forum/thread page's toggle in step.
				queryClient.invalidateQueries({
					queryKey:
						kind === "forum"
							? forumQueryOptions(id).queryKey
							: threadQueryOptions(id).queryKey,
					exact: true,
				}),
			]),
	});

	const tree = buildSubscriptionTree(subscriptions.forums);
	const isEmpty =
		!subscriptions.forums.some((forum) => forum.subscribed) &&
		subscriptions.thread_groups.length === 0;

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Manage Subscriptions
			</h1>
			<div className={styles["content"]} style={{ marginInline: hbMargined.margin }}>
				<p>
					<Link to="/forums/{-$forumId}" params={{ forumId: 0 }}>
						Return to forums
					</Link>
				</p>

				<section className={styles["email-setting"]}>
					<div className={styles["setting-row"]}>
						<label id="forum-sub-type-label" htmlFor="forum-sub-type">
							Send me
						</label>
						<Select
							id="forum-sub-type"
							ariaLabelledBy="forum-sub-type-label"
							items={FORUM_SUB_TYPE_OPTIONS}
							getId={(option) => option.id}
							getLabel={(option) => option.label}
							selectedId={forumSubType}
							isDisabled={settingMutation.isPending}
							onChange={(id) => settingMutation.mutate(id as ForumSubType)}
						/>
						<FadeOut active={saved} className={styles["saved"]}>
							Saved
						</FadeOut>
					</div>
					{settingMutation.isError && (
						<div className="error" role="alert">
							{subscriptionErrorMessage(
								settingMutation.error,
								"Couldn't save your email setting. Please try again.",
							)}
						</div>
					)}
					<ul className={styles["option-help"]}>
						{FORUM_SUB_TYPE_OPTIONS.map((option) => (
							<li key={option.id}>
								<strong>{option.label}:</strong> {option.description}
							</li>
						))}
					</ul>
				</section>

				{unsubscribeMutation.isError && (
					<div className="error" role="alert">
						{subscriptionErrorMessage(unsubscribeMutation.error)}
					</div>
				)}

				{isEmpty ? (
					<p>
						You aren't subscribed to anything yet. Use the "Subscribe to forum" or
						"Subscribe to thread" link at the bottom of a forum or at the top of a
						thread to get emails about new activity there.
					</p>
				) : (
					<>
						<section>
							<h2>Forums</h2>
							{tree.length > 0 ? (
								<ul className={`${styles["tree"]} ${styles["root"]}`}>
									{tree.map((node) => (
										<ForumNode
											key={node.id}
											node={node}
											onUnsubscribe={unsubscribeMutation.mutate}
											pending={unsubscribeMutation.isPending}
										/>
									))}
								</ul>
							) : (
								<p>No forum subscriptions.</p>
							)}
						</section>

						<section>
							<h2>Threads</h2>
							{subscriptions.thread_groups.length > 0 ? (
								subscriptions.thread_groups.map((group) => (
									<div key={group.forum_id} className={styles["thread-group"]}>
										<h3>
											<Link
												to="/forums/{-$forumId}"
												params={{ forumId: group.forum_id }}
											>
												{group.forum_title}
											</Link>
										</h3>
										<ul className={styles["tree"]}>
											{group.threads.map((thread) => (
												<li key={thread.id} className={styles["row"]}>
													<Link
														to="/forums/thread/$threadId"
														params={{ threadId: thread.id }}
														className={styles["title"]}
													>
														{thread.title}
													</Link>
													<button
														type="button"
														className="link-btn"
														disabled={unsubscribeMutation.isPending}
														aria-label={`Unsubscribe from thread ${thread.title}`}
														onClick={() =>
															unsubscribeMutation.mutate({
																kind: "thread",
																id: thread.id,
															})
														}
													>
														Unsubscribe
													</button>
												</li>
											))}
										</ul>
									</div>
								))
							) : (
								<p>No thread subscriptions.</p>
							)}
						</section>
					</>
				)}
			</div>
		</div>
	);
}
