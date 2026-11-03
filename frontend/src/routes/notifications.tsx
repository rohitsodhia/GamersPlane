import {
	useMutation,
	useQueryClient,
	useSuspenseInfiniteQuery,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Button } from "react-aria-components";
import { NotificationEntry } from "#/components/NotificationEntry";
import { buildNotificationItems } from "#/components/notificationText";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { markAllMentionsRead, meNotificationsPagesQueryOptions } from "#/queries/me";
import styles from "./notifications.module.css";

export const Route = createFileRoute("/notifications")({
	beforeLoad: requireAuth,
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureInfiniteQueryData(meNotificationsPagesQueryOptions),
			location,
		),
	errorComponent: NotificationsError,
	component: RouteComponent,
});

function NotificationsError() {
	return (
		<div className="error" role="alert">
			Couldn't load your notifications. Please try again.
		</div>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const queryClient = useQueryClient();
	const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isFetchNextPageError } =
		useSuspenseInfiniteQuery(meNotificationsPagesQueryOptions);
	// Invites and pending games ride along on every page; the first is current.
	const first = data.pages[0];
	const items = buildNotificationItems({
		pending: first.pending,
		invites: first.invites,
		mentions: data.pages.flatMap((page) => page.mentions),
	});
	const hasUnread = items.some((item) => item.kind === "mention" && !item.read);

	const markAllRead = useMutation({
		mutationFn: markAllMentionsRead,
		onSettled: () =>
			queryClient.invalidateQueries({ queryKey: ["me", "notifications"] }),
	});

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Notifications
			</h1>
			<div style={{ marginInline: hbMargined.margin }}>
				{hasUnread && (
					<Button
						className="skew-btn"
						onPress={() => markAllRead.mutate()}
						isDisabled={markAllRead.isPending}
					>
						Mark all read
					</Button>
				)}
				{markAllRead.isError && (
					<div className="error" role="alert">
						Couldn't mark your mentions as read. Please try again.
					</div>
				)}
				{items.length === 0 ? (
					<p>Nothing needs your attention.</p>
				) : (
					<ul className={styles["list"]}>
						{items.map((item) => (
							<li key={item.key} className={styles["item"]}>
								<NotificationEntry item={item} />
							</li>
						))}
					</ul>
				)}
				{isFetchNextPageError && (
					<div className="error" role="alert">
						Couldn't load more mentions. Please try again.
					</div>
				)}
				{hasNextPage && (
					<Button
						className="skew-btn"
						onPress={() => fetchNextPage()}
						isDisabled={isFetchingNextPage}
					>
						Load more
					</Button>
				)}
			</div>
		</div>
	);
}
