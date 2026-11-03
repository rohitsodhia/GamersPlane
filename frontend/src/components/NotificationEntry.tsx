import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Button } from "react-aria-components";
import { dismissMention, markMentionRead } from "#/queries/me";
import styles from "./NotificationEntry.module.css";
import type { NotificationItem } from "./notificationText";

/**
 * One bell/page entry. Render it as the only content of the row's `<li>`: a
 * mention is a link plus a dismiss button (siblings, so the button never sits
 * inside the `<a>`), and the row is laid out by the parent's flex styles.
 *
 * A mention marks itself read on click, in the background: the Link navigates
 * to the post right away, and a failed mark-read never holds that up (the bell
 * just refetches and still shows it). Dismissing hides it for good, so a failure
 * there is shown. The dismiss button carries `data-keep-open` so the bell's
 * popover stays open when it is pressed.
 */
export function NotificationEntry({ item }: { item: NotificationItem }) {
	const queryClient = useQueryClient();
	const invalidate = () =>
		queryClient.invalidateQueries({ queryKey: ["me", "notifications"] });
	const markRead = useMutation({
		mutationFn: markMentionRead,
		onSettled: invalidate,
	});
	const dismiss = useMutation({
		mutationFn: dismissMention,
		onSettled: invalidate,
	});

	if (item.kind === "game") {
		return (
			<Link to="/games/$gameId" params={{ gameId: item.gameId }}>
				{item.text}
			</Link>
		);
	}

	return (
		<>
			<Link
				to="/forums/thread/$threadId"
				params={{ threadId: item.threadId }}
				search={{ p: item.postId }}
				className={item.read ? undefined : styles["unread"]}
				onClick={() => {
					if (!item.read) markRead.mutate(item.eventId);
				}}
			>
				<strong>{item.actorName}</strong> mentioned you in <em>{item.threadTitle}</em>
			</Link>
			<Button
				className={styles["dismiss"]}
				data-keep-open
				aria-label={`Dismiss notification from ${item.actorName} in ${item.threadTitle}`}
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
