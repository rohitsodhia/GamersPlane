import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { markMentionRead } from "#/queries/me";
import styles from "./NotificationEntry.module.css";
import type { NotificationItem } from "./notificationText";

/**
 * The link for one bell/page entry. A mention marks itself read on click, in
 * the background: the Link navigates to the post right away, and a failed
 * mark-read never holds that up (the bell just refetches and still shows it).
 */
export function NotificationEntry({ item }: { item: NotificationItem }) {
	const queryClient = useQueryClient();
	const markRead = useMutation({
		mutationFn: markMentionRead,
		onSettled: () =>
			queryClient.invalidateQueries({ queryKey: ["me", "notifications"] }),
	});

	if (item.kind === "game") {
		return (
			<Link to="/games/$gameId" params={{ gameId: item.gameId }}>
				{item.text}
			</Link>
		);
	}

	return (
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
	);
}
