import { type QueryClient, queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

export type ReportTargetType =
	| "post"
	| "thread"
	| "user"
	| "user_avatar"
	| "character"
	| "character_avatar"
	| "game"
	| "game_background"
	| "npc_image";

export type ReportReason =
	| "illegal_content"
	| "copyright"
	| "harassment"
	| "spam"
	| "guidelines"
	| "other";

export const REPORT_REASON_LABELS: Record<ReportReason, string> = {
	illegal_content: "Illegal content",
	copyright: "Copyright",
	harassment: "Harassment",
	spam: "Spam",
	guidelines: "Guidelines violation",
	other: "Other",
};

export const REPORT_REASONS = Object.keys(REPORT_REASON_LABELS) as ReportReason[];

/** Matches the API's `REPORT_TEXT_MAX`. */
export const REPORT_DETAILS_MAX = 1000;

export type ReportInput = {
	target_type: ReportTargetType;
	target_id: number;
	reason: ReportReason;
	details?: string;
};

const throwApiError = async (res: Response): Promise<never> => {
	const errors = await res
		.json()
		.then((body) => body.errors ?? [])
		.catch(() => []);
	throw new ApiError(res.status, errors);
};

export const fileReport = async (
	data: ReportInput,
): Promise<{ id: number; status: string }> => {
	const res = await apiFetch("/reports", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) return throwApiError(res);
	return res.json();
};

export type ReportStatus = "open" | "actioned" | "dismissed";

export const REPORT_STATUSES: ReportStatus[] = ["open", "actioned", "dismissed"];

export const REPORT_TARGET_TYPES: ReportTargetType[] = [
	"post",
	"thread",
	"user",
	"user_avatar",
	"character",
	"character_avatar",
	"game",
	"game_background",
	"npc_image",
];

export const REPORT_TARGET_LABELS: Record<ReportTargetType, string> = {
	post: "Post",
	thread: "Thread",
	user: "User",
	user_avatar: "User avatar",
	character: "Character",
	character_avatar: "Character avatar",
	game: "Game",
	game_background: "Game background",
	npc_image: "NPC image",
};

export const IMAGE_TARGET_TYPES: ReportTargetType[] = [
	"user_avatar",
	"character_avatar",
	"game_background",
	"npc_image",
];

/** Matches the API's `REPORT_GROUPS_PER_PAGE`. */
export const REPORT_GROUPS_PER_PAGE = 25;

/** What the API captured about the target when the report was filed. */
export type ReportSnapshot = Record<string, unknown>;

export type ReportGroup = {
	target_type: ReportTargetType;
	target_id: number;
	status: ReportStatus;
	count: number;
	reason: ReportReason;
	first_reported_at: string;
	last_reported_at: string;
	latest_snapshot: ReportSnapshot;
};

export type ReportGroupsResponse = { groups: ReportGroup[]; total: number };

export type ReportUser = { id: number; username: string };

export type TargetReport = {
	id: number;
	reporter: ReportUser;
	reason: ReportReason;
	details: string | null;
	status: ReportStatus;
	created_at: string;
	resolved_by: ReportUser | null;
	resolved_at: string | null;
	resolution_note: string | null;
	snapshot: ReportSnapshot;
	has_snapshot_file: boolean;
};

export type TargetReportsResponse = {
	target_type: ReportTargetType;
	target_id: number;
	reports: TargetReport[];
};

export const reportGroupsQueryOptions = (status: ReportStatus, page: number) =>
	queryOptions({
		queryKey: ["reports", "groups", status, page],
		queryFn: async (): Promise<ReportGroupsResponse> => {
			const res = await apiFetch(`/reports?status=${status}&page=${page}`);
			if (!res.ok) return throwApiError(res);
			return res.json();
		},
	});

export const targetReportsQueryOptions = (type: ReportTargetType, id: number) =>
	queryOptions({
		queryKey: ["reports", "target", type, id],
		queryFn: async (): Promise<TargetReportsResponse> => {
			const res = await apiFetch(`/reports/${type}/${id}`);
			if (!res.ok) return throwApiError(res);
			return res.json();
		},
	});

/** The quarantined copy of a reported image, as an object URL (the endpoint needs auth). */
export const reportSnapshotImageQueryOptions = (reportId: number) =>
	queryOptions({
		queryKey: ["reports", "snapshot-file", reportId],
		queryFn: async (): Promise<string> => {
			const res = await apiFetch(`/reports/${reportId}/snapshot-file`);
			if (!res.ok) return throwApiError(res);
			return URL.createObjectURL(await res.blob());
		},
		staleTime: Number.POSITIVE_INFINITY,
	});

type TargetRef = { type: ReportTargetType; id: number };

export const resolveReports = async ({
	type,
	id,
	status,
	note,
}: TargetRef & {
	status: "actioned" | "dismissed";
	note?: string;
}): Promise<{ resolved: number }> => {
	const res = await apiFetch(`/reports/${type}/${id}/resolve`, {
		method: "POST",
		body: JSON.stringify({ status, note: note || undefined }),
	});
	if (!res.ok) return throwApiError(res);
	return res.json();
};

export const removeReportedImage = async ({ type, id }: TargetRef): Promise<void> => {
	const res = await apiFetch(`/reports/${type}/${id}/remove-image`, {
		method: "POST",
	});
	if (!res.ok) return throwApiError(res);
};

export const invalidateReports = (queryClient: QueryClient) =>
	queryClient.invalidateQueries({ queryKey: ["reports"] });

/** Turns a failed staff report action into a message that's safe to show. */
export const reportActionErrorMessage = (error: unknown): string => {
	if (error instanceof ApiError) {
		if (error.status === 403) return "You don't have permission to manage reports.";
		if (error.status === 404) {
			return "There are no open reports on this item (or it no longer exists). Reload the page.";
		}
		const details = error.errors.map((e) => e.detail).filter(Boolean);
		if (error.status === 422 && details.length > 0) return details.join(" ");
	}
	return "Something went wrong. Please try again.";
};
