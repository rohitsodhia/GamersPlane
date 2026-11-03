// A mention node holds only a `userId`; the name comes from the post's
// `content_mentions`, so a renamed user's old mentions follow the rename.

export type ContentMention = {
	id: number;
	username: string;
};

export type MentionLookup = Record<number, string>;

export const DELETED_MENTION_NAME = "[deleted]";

// The users as an id-keyed lookup of usernames, for rendering saved posts.
export function mentionLookup(mentions: readonly ContentMention[] = []): MentionLookup {
	return Object.fromEntries(mentions.map((user) => [user.id, user.username]));
}

function validId(userId: unknown): userId is number {
	return typeof userId === "number" && Number.isInteger(userId) && userId > 0;
}

// The username a mention shows, or null for a missing, malformed, or unlisted
// user (one deleted, or never saved with the post).
export function mentionName(userId: unknown, lookup: MentionLookup): string | null {
	return validId(userId) ? (lookup[userId] ?? null) : null;
}

// The mention's text: "@name", or "@[deleted]" when the user can't be found.
export function mentionLabel(userId: unknown, lookup: MentionLookup): string {
	return `@${mentionName(userId, lookup) ?? DELETED_MENTION_NAME}`;
}

// The profile a mention links to; null for an unknown user, who isn't linked.
export function mentionHref(userId: unknown, lookup: MentionLookup): string | null {
	return mentionName(userId, lookup) === null ? null : `/user/${userId}`;
}

// `current` moved by `delta` through `count` items, wrapping at both ends (for the
// picker's up/down keys). 0 when there is nothing to move through.
export function stepIndex(current: number, delta: number, count: number): number {
	if (count <= 0) return 0;
	return (((current + delta) % count) + count) % count;
}

// `existing` plus any of `added` it doesn't list yet (by id), keeping order.
export function addMentions(
	existing: readonly ContentMention[],
	added: readonly ContentMention[],
): ContentMention[] {
	const known = new Set(existing.map((user) => user.id));
	return [...existing, ...added.filter((user) => !known.has(user.id))];
}

// The editor's view of its users: the post's own `content_mentions`, then anyone
// picked in this editing session (who the post doesn't list yet).
export function findMentionNames(
	picked: readonly ContentMention[],
	fallback: readonly ContentMention[],
): MentionLookup {
	return { ...mentionLookup(fallback), ...mentionLookup(picked) };
}
