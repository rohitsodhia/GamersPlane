import type { ReportSnapshot, ReportTargetType } from "#/queries/reports";

const EXCERPT_MAX = 80;

const text = (value: unknown): string | null =>
	typeof value === "string" && value.trim() ? value.trim() : null;

const positiveInt = (value: unknown): number | null =>
	typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;

/** `body` with whitespace collapsed, cut to a short excerpt. */
const excerpt = (body: string): string => {
	const flat = body.replace(/\s+/g, " ");
	return flat.length > EXCERPT_MAX ? `${flat.slice(0, EXCERPT_MAX).trimEnd()}…` : flat;
};

/** A short human description of a reported thing, from the snapshot taken at report time. */
export function describeReportTarget(
	targetType: ReportTargetType,
	snapshot: ReportSnapshot,
): string {
	switch (targetType) {
		case "post":
		case "thread": {
			const title = text(snapshot.title);
			if (title) return title;
			const body = text(snapshot.body_text);
			return body ? excerpt(body) : "(no text)";
		}
		case "user":
			return text(snapshot.username) ?? "Unknown user";
		case "user_avatar": {
			const username = text(snapshot.username);
			return username ? `Avatar of ${username}` : "Avatar";
		}
		case "character":
			return text(snapshot.name) ?? "Unnamed character";
		case "game":
			return text(snapshot.title) ?? "Untitled game";
		case "game_background": {
			const title = text(snapshot.title);
			return title ? `Background of ${title}` : "Background";
		}
		case "character_avatar":
		case "npc_image":
			return "Image";
	}
}

export type ReportTargetLink =
	| { to: "/forums/thread/$threadId"; params: { threadId: number }; hash?: string }
	| { to: "/user/$userId"; params: { userId: number } }
	| { to: "/characters/$characterId"; params: { characterId: number } }
	| { to: "/games/$gameId"; params: { gameId: number } };

/**
 * Where to look at a reported thing, or null when it has no page (NPC images) or
 * the snapshot lacks the id needed to build one.
 */
export function reportTargetLink(
	targetType: ReportTargetType,
	targetId: number,
	snapshot: ReportSnapshot,
): ReportTargetLink | null {
	switch (targetType) {
		case "post": {
			const threadId = positiveInt(snapshot.thread_id);
			return threadId
				? {
						to: "/forums/thread/$threadId",
						params: { threadId },
						hash: `post-${targetId}`,
					}
				: null;
		}
		case "thread":
			return { to: "/forums/thread/$threadId", params: { threadId: targetId } };
		case "user":
		case "user_avatar":
			return { to: "/user/$userId", params: { userId: targetId } };
		case "character":
			return { to: "/characters/$characterId", params: { characterId: targetId } };
		case "character_avatar": {
			const characterId = positiveInt(snapshot.character_id);
			return characterId
				? { to: "/characters/$characterId", params: { characterId } }
				: null;
		}
		case "game":
			return { to: "/games/$gameId", params: { gameId: targetId } };
		case "game_background": {
			const gameId = positiveInt(snapshot.game_id) ?? targetId;
			return { to: "/games/$gameId", params: { gameId } };
		}
		case "npc_image":
			return null;
	}
}
