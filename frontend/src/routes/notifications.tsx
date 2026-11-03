import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { buildNotificationItems } from "#/components/notificationText";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { meNotificationsQueryOptions } from "#/queries/me";
import styles from "./notifications.module.css";

export const Route = createFileRoute("/notifications")({
	beforeLoad: requireAuth,
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(meNotificationsQueryOptions),
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
	const { data: notifications } = useSuspenseQuery(meNotificationsQueryOptions);
	const items = buildNotificationItems(notifications);

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Notifications
			</h1>
			<div style={{ marginInline: hbMargined.margin }}>
				{items.length === 0 ? (
					<p>Nothing needs your attention.</p>
				) : (
					<ul className={styles["list"]}>
						{items.map((item) => (
							<li key={item.key} className={styles["item"]}>
								<Link to="/games/$gameId" params={{ gameId: item.gameId }}>
									{item.text}
								</Link>
							</li>
						))}
					</ul>
				)}
			</div>
		</div>
	);
}
