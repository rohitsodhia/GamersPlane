import type { ForumPermission } from "#/queries/forums";
import type { ThreadDetails } from "#/queries/threads";

// Mirrors the API's checks (create_post, check_post_change): moderators can do
// anything; everyone else needs the permission and an unlocked thread, and (for
// edit/delete) to be the post's author.

export function canWrite(thread: ThreadDetails) {
	return (
		thread.permissions.includes("forum_moderate") ||
		(!thread.options.locked && thread.permissions.includes("forum_write"))
	);
}

export function canChangePost(
	thread: ThreadDetails,
	authorId: number,
	userId: number | undefined,
	permission: ForumPermission,
) {
	return (
		thread.permissions.includes("forum_moderate") ||
		(!thread.options.locked &&
			authorId === userId &&
			thread.permissions.includes(permission))
	);
}
