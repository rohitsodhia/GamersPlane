import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Button } from "react-aria-components";
import {
	dismissNotification,
	markNotificationRead,
	type Notification,
} from "#/queries/me";
import styles from "./NotificationEntry.module.css";
import { notificationPlainText, notificationSegments } from "./notificationText";

/**
 * One bell/page entry. Render it as the only content of the row's `<li>`: a
 * link plus a dismiss button (siblings, so the button never sits inside the
 * `<a>`), and the row is laid out by the parent's flex styles.
 *
 * An unread entry marks itself read on click, in the background: the Link
 * navigates right away, and a failed mark-read never holds that up (the bell
 * just refetches and still shows it). Dismissing hides it for good, so a failure
 * there is shown. The dismiss button carries `data-keep-open` so the bell's
 * popover stays open when it is pressed.
 */
export function NotificationEntry({ item }: { item: Notification }) {
	const queryClient = useQueryClient();
	const invalidate = () =>
		queryClient.invalidateQueries({ queryKey: ["me", "notifications"] });
	const markRead = useMutation({
		mutationFn: markNotificationRead,
		onSettled: invalidate,
	});
	const dismiss = useMutation({
		mutationFn: dismissNotification,
		onSettled: invalidate,
	});

	const className = item.read ? undefined : styles["unread"];
	const onClick = () => {
		if (!item.read) markRead.mutate(item.eventId);
	};
	const content = notificationSegments(item).map((segment, index) => {
		const key = `${index}-${segment.text}`;
		if (segment.style === "strong") return <strong key={key}>{segment.text}</strong>;
		if (segment.style === "em") return <em key={key}>{segment.text}</em>;
		return <span key={key}>{segment.text}</span>;
	});

	return (
		<>
			{item.type === "mention" ? (
				<Link
					to="/forums/thread/$threadId"
					params={{ threadId: item.threadId }}
					search={{ p: item.postId }}
					className={className}
					onClick={onClick}
				>
					{content}
				</Link>
			) : (
				<Link
					to="/games/$gameId"
					params={{ gameId: item.gameId }}
					className={className}
					onClick={onClick}
				>
					{content}
				</Link>
			)}
			<Button
				className={styles["dismiss"]}
				data-keep-open
				aria-label={`Dismiss: ${notificationPlainText(item)}`}
				isDisabled={dismiss.isPending}
				onPress={() => dismiss.mutate(item.eventId)}
			>
				<span aria-hidden="true">×</span>
			</Button>
			{dismiss.isError && (
				<div className={`error ${styles["dismiss-error"]}`} role="alert">
					Couldn't dismiss that notification. Please try again.
				</div>
			)}
		</>
	);
}
