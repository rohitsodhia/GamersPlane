import {
	useMutation,
	useQueryClient,
	useSuspenseInfiniteQuery,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Button } from "react-aria-components";
import { NotificationEntry } from "#/components/NotificationEntry";
import { flattenPages } from "#/components/notificationText";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	markAllNotificationsRead,
	meNotificationsPagesQueryOptions,
} from "#/queries/me";
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
	const items = flattenPages(data.pages);
	const hasUnread = items.some((item) => !item.read);

	const markAllRead = useMutation({
		mutationFn: markAllNotificationsRead,
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
						Couldn't mark your notifications as read. Please try again.
					</div>
				)}
				{items.length === 0 ? (
					<p>Nothing needs your attention.</p>
				) : (
					<ul className={styles["list"]}>
						{items.map((item) => (
							<li key={item.eventId} className={styles["item"]}>
								<NotificationEntry item={item} />
							</li>
						))}
					</ul>
				)}
				{isFetchNextPageError && (
					<div className="error" role="alert">
						Couldn't load more notifications. Please try again.
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
