import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
	setForumSubscribed,
	setThreadSubscribed,
	subscriptionErrorMessage,
} from "#/queries/forumSubscriptions";
import { forumQueryOptions } from "#/queries/forums";
import { threadQueryOptions } from "#/queries/threads";

// Subscribe/unsubscribe link-button for the forum or thread page. Shows an error
// beneath it when the request fails.
export function SubscribeToggle({
	kind,
	id,
	subscribed,
}: {
	kind: "forum" | "thread";
	id: number;
	subscribed: boolean;
}) {
	const queryClient = useQueryClient();
	const mutation = useMutation({
		mutationFn: () =>
			kind === "forum"
				? setForumSubscribed(id, !subscribed)
				: setThreadSubscribed(id, !subscribed),
		onSuccess: () =>
			Promise.all([
				queryClient.invalidateQueries({
					queryKey:
						kind === "forum"
							? forumQueryOptions(id).queryKey
							: threadQueryOptions(id).queryKey,
					exact: true,
				}),
				queryClient.invalidateQueries({ queryKey: ["subscriptions"] }),
			]),
	});

	return (
		<>
			<button
				type="button"
				className="link-btn"
				disabled={mutation.isPending}
				onClick={() => mutation.mutate()}
			>
				{subscribed ? "Unsubscribe from" : "Subscribe to"} {kind}
			</button>
			{mutation.isError && (
				<div className="error" role="alert">
					{subscriptionErrorMessage(mutation.error)}
				</div>
			)}
		</>
	);
}
