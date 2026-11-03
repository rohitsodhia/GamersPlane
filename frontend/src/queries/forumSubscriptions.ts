import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

export type ForumSubType = "all" | "new content" | "none";

// The one place the subscription email options are worded, for the profile
// settings and the Manage Subscriptions page.
export const FORUM_SUB_TYPE_OPTIONS: {
	id: ForumSubType;
	label: string;
	description: string;
}[] = [
	{
		id: "all",
		label: "Every post",
		description: "An email for every new post, new thread, and major edit.",
	},
	{
		id: "new content",
		label: "New activity only",
		description:
			"A short notice for each new thread, and for the first new activity in a thread until you visit it again.",
	},
	{
		id: "none",
		label: "No emails",
		description: "Keep your subscriptions but send no email.",
	},
];

export type SubscribedForum = {
	id: number;
	title: string;
	parent_id: number | null;
	// False for an ancestor listed only so the tree can be built.
	subscribed: boolean;
};

export type SubscribedThread = {
	id: number;
	title: string;
};

export type SubscribedThreadGroup = {
	forum_id: number;
	forum_title: string;
	threads: SubscribedThread[];
};

export type SubscriptionsResponse = {
	forums: SubscribedForum[];
	thread_groups: SubscribedThreadGroup[];
};

export type SubscriptionTreeNode = SubscribedForum & {
	children: SubscriptionTreeNode[];
};

// Nests the flat list by parent_id. A forum whose parent isn't in the list is
// treated as top level, so nothing the API returns is dropped.
export const buildSubscriptionTree = (
	forums: SubscribedForum[],
): SubscriptionTreeNode[] => {
	const nodes = new Map<number, SubscriptionTreeNode>(
		forums.map((forum) => [forum.id, { ...forum, children: [] }]),
	);
	const roots: SubscriptionTreeNode[] = [];
	for (const forum of forums) {
		const node = nodes.get(forum.id) as SubscriptionTreeNode;
		const parent = forum.parent_id === null ? undefined : nodes.get(forum.parent_id);
		(parent ? parent.children : roots).push(node);
	}
	return roots;
};

export const subscriptionsQueryOptions = queryOptions({
	queryKey: ["subscriptions"],
	queryFn: async (): Promise<SubscriptionsResponse> => {
		const res = await apiFetch("/me/subscriptions");
		if (!res.ok) {
			const { errors } = await res.json().catch(() => ({ errors: [] }));
			throw new ApiError(res.status, errors);
		}
		return res.json();
	},
	staleTime: 0,
});

const subscriptionRequest = async (path: string, method: "PUT" | "DELETE") => {
	const res = await apiFetch(path, { method });
	if (!res.ok) {
		const { errors } = await res.json().catch(() => ({ errors: [] }));
		throw new ApiError(res.status, errors);
	}
};

export const setForumSubscribed = (forumId: number, subscribed: boolean) =>
	subscriptionRequest(`/forums/${forumId}/subscription`, subscribed ? "PUT" : "DELETE");

export const setThreadSubscribed = (threadId: number, subscribed: boolean) =>
	subscriptionRequest(
		`/threads/${threadId}/subscription`,
		subscribed ? "PUT" : "DELETE",
	);

export const subscriptionErrorMessage = (
	error: unknown,
	fallback = "Couldn't update the subscription. Please try again.",
) =>
	error instanceof ApiError && error.errors.length > 0
		? error.errors.map((e) => e.detail).join(" ")
		: fallback;
