import {
	infiniteQueryOptions,
	type QueryClient,
	queryOptions,
} from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";
import type { ForumSubType } from "#/queries/forumSubscriptions";
import { useAuthStore } from "#/stores/auth";

export type PostSide = "r" | "l" | "c";

export type MeResponse = {
	id: number;
	username: string;
	avatar: string;
	acp: boolean;
	// Moderates at least one forum. Forum moderation is scoped, so it isn't in
	// `permissions`.
	forumModerate: boolean;
	// An admin, or moderates at least one site (non-game) forum. Can create site
	// roles.
	siteModerate: boolean;
	// An admin, or moderates the games forum or one of its ancestors. These users
	// get the player/moderator mode switch.
	gameModerate: boolean;
	// Can reach the Roles page: a global admin, a site moderator, the owner of a
	// site role, or holder of a scoped role_admin grant.
	roleAdmin: boolean;
	permissions: string[];
};

// Global permission verb that satisfies every check (mirrors the API's ADMIN_OVERRIDE).
const ADMIN_VERB = "admin";

/**
 * True if the current user holds any of `verbs` as a global permission. Holding
 * the `admin` verb satisfies any check.
 */
export const hasPermission = (
	me: Pick<MeResponse, "permissions"> | null | undefined,
	...verbs: string[]
): boolean => {
	if (!me) return false;
	if (me.permissions.includes(ADMIN_VERB)) return true;
	return verbs.some((verb) => me.permissions.includes(verb));
};

type MeFullApiResponse = MeResponse & {
	email: string;
	joinDate: string;
	pronouns: string | null;
	birthday: string | null;
	showAge: boolean | null;
	location: string | null;
	pmMail: boolean | null;
	newGameMail: boolean | null;
	gmMail: boolean | null;
	gameMail: boolean | null;
	forumSubType: ForumSubType;
	postSide: PostSide;
	lookingForAGame: boolean | null;
	gameInterests: string | null;
};

type MeFullResponse = Omit<MeFullApiResponse, "joinDate"> & {
	joinDate: Date;
};

type MeHeaderResponse = {
	characters: unknown[];
	games: unknown[];
	pmCount: number;
};

// A 403 from a `/me*` endpoint means the current token isn't accepted as a
// logged-in user (missing/invalid/expired/rejected) — there's no partial
// permission model on these routes, so it always means "log out", not "some
// feature is unavailable." Clear it so the app falls back to the logged-out
// state instead of getting stuck retrying a token that will never work.
const handleMeError = async (res: Response): Promise<never> => {
	if (res.status === 403) {
		useAuthStore.getState().setToken(null);
	}
	const errors = await res
		.json()
		.then((body) => body.errors)
		.catch(() => []);
	throw new ApiError(res.status, errors);
};

const fetchMe = async (): Promise<MeResponse> => {
	const res = await apiFetch("/me");
	if (!res.ok) return handleMeError(res);
	return res.json();
};

const fetchMeHeader = async (): Promise<MeHeaderResponse> => {
	const res = await apiFetch("/me/header");
	if (!res.ok) return handleMeError(res);
	return res.json();
};

const fetchMeFull = async (): Promise<MeFullResponse> => {
	const res = await apiFetch("/me?full=true");
	if (!res.ok) return handleMeError(res);
	const data: MeFullApiResponse = await res.json();
	return { ...data, joinDate: new Date(data.joinDate) };
};

// A 403 means the token is bad and retrying won't change that — let every
// other status fall back to react-query's default retry behavior.
const retryUnlessForbidden = (failureCount: number, error: unknown) =>
	!(error instanceof ApiError && error.status === 403) && failureCount < 3;

export const meQueryOptions = queryOptions({
	queryKey: ["me"],
	queryFn: fetchMe,
	staleTime: 1000 * 60 * 5,
	retry: retryUnlessForbidden,
});

export const meHeaderQueryOptions = queryOptions({
	queryKey: ["me", "header"],
	queryFn: fetchMeHeader,
	staleTime: Number.POSITIVE_INFINITY,
	retry: retryUnlessForbidden,
});

type NotificationBase = {
	eventId: number;
	actor: { id: number; username: string };
	createdAt: string;
	read: boolean;
};

export type MentionNotification = NotificationBase & {
	type: "mention";
	threadId: number;
	threadTitle: string;
	postId: number;
	forumId: number;
};

export type GameInviteNotification = NotificationBase & {
	type: "game_invite";
	gameId: number;
	gameTitle: string;
};

export type GameApplicationNotification = NotificationBase & {
	type: "game_application";
	gameId: number;
	gameTitle: string;
};

export type CharacterSubmittedNotification = NotificationBase & {
	type: "character_submitted";
	gameId: number;
	gameTitle: string;
	characterId: number;
	characterName: string;
};

export type Notification =
	| MentionNotification
	| GameInviteNotification
	| GameApplicationNotification
	| CharacterSubmittedNotification;

export type MeNotificationsResponse = {
	// Every type interleaved, newest first; read ones included.
	items: Notification[];
	hasMore: boolean;
	// Opaque; pass it back untouched as `before`.
	nextCursor: string | null;
	// Every unread, undismissed item of all types (not only this page's).
	count: number;
};

const fetchMeNotifications = async (
	before?: string,
): Promise<MeNotificationsResponse> => {
	const query = before === undefined ? "" : `?before=${encodeURIComponent(before)}`;
	const res = await apiFetch(`/me/notifications${query}`);
	if (!res.ok) return handleMeError(res);
	return res.json();
};

// Stored server-side per user, so anything that creates one (or changes what
// it shows) should invalidate this key.
// Nested under "me" so logout and a blanket ["me"] invalidation cover it too.
export const meNotificationsQueryOptions = queryOptions({
	queryKey: ["me", "notifications"],
	queryFn: () => fetchMeNotifications(),
	staleTime: 1000 * 60,
	// Poll every two minutes while the tab is visible; sockets would replace this.
	refetchInterval: 1000 * 60 * 2,
	retry: retryUnlessForbidden,
});

// The /notifications page's paged view. Its key extends the first-page key, so
// invalidating ["me", "notifications"] refreshes the bell and this page together.
export const meNotificationsPagesQueryOptions = infiniteQueryOptions({
	queryKey: ["me", "notifications", "pages"],
	queryFn: ({ pageParam }) => fetchMeNotifications(pageParam),
	initialPageParam: undefined as string | undefined,
	getNextPageParam: (lastPage) =>
		lastPage.hasMore ? (lastPage.nextCursor ?? undefined) : undefined,
	staleTime: 1000 * 60,
	retry: retryUnlessForbidden,
});

/** Marks one notification read. A 404 means it is already gone, which is fine. */
export const markNotificationRead = async (eventId: number): Promise<void> => {
	const res = await apiFetch(`/me/notifications/${eventId}/read`, {
		method: "POST",
	});
	if (!res.ok && res.status !== 404) return handleMeError(res);
};

/** Hides one notification for good (reading it too). A 404 means it is already gone. */
export const dismissNotification = async (eventId: number): Promise<void> => {
	const res = await apiFetch(`/me/notifications/${eventId}/dismiss`, {
		method: "POST",
	});
	if (!res.ok && res.status !== 404) return handleMeError(res);
};

export const markAllNotificationsRead = async (): Promise<void> => {
	const res = await apiFetch("/me/notifications/read-all", {
		method: "POST",
	});
	if (!res.ok) return handleMeError(res);
};

// Nested under the "me" key so invalidating ["me"] invalidates this too.
export const meFullQueryOptions = queryOptions({
	queryKey: ["me", "full"],
	queryFn: fetchMeFull,
	staleTime: 1000 * 60 * 5,
	retry: retryUnlessForbidden,
});

// Refetches the full profile once and seeds both the "me" and "me full" caches
// from that single response, instead of invalidating both keys and firing two requests.
export const refreshMe = async (queryClient: QueryClient) => {
	const full = await fetchMeFull();
	queryClient.setQueryData(meFullQueryOptions.queryKey, full);
	queryClient.setQueryData(meQueryOptions.queryKey, {
		id: full.id,
		username: full.username,
		avatar: full.avatar,
		acp: full.acp,
		forumModerate: full.forumModerate,
		siteModerate: full.siteModerate,
		gameModerate: full.gameModerate,
		roleAdmin: full.roleAdmin,
		permissions: full.permissions,
	});
};

export const updateUserSettings = async (userData: {
	pronouns?: string;
	birthday?: string;
	showAge?: boolean;
	location?: string;
	pmMail?: boolean;
	newGameMail?: boolean;
	gmMail?: boolean;
	gameMail?: boolean;
	forumSubType?: ForumSubType;
	postSide?: PostSide;
	lookingForAGame?: boolean;
	gameInterests?: string;
}) => {
	const res = await apiFetch("/me", {
		method: "POST",
		body: JSON.stringify(userData),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export type LfgSystem = {
	id: string;
	name: string;
};

type LfgSystemsResponse = { systems: LfgSystem[] };

// Nested under "me" so invalidating ["me"] refreshes it too.
export const lfgSystemsQueryOptions = queryOptions({
	queryKey: ["me", "lfg-systems"],
	queryFn: async (): Promise<LfgSystemsResponse> => {
		const res = await apiFetch("/me/lfg-systems");
		if (!res.ok) return handleMeError(res);
		return res.json();
	},
	staleTime: 1000 * 60 * 5,
	retry: retryUnlessForbidden,
});

// Replaces the whole set. Callers seed the cache from the response so every
// picker instance sharing lfgSystemsQueryOptions updates at once.
export const updateLfgSystems = async (
	systems: string[],
): Promise<LfgSystemsResponse> => {
	const res = await apiFetch("/me/lfg-systems", {
		method: "POST",
		body: JSON.stringify({ systems }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const updateUserPassword = async (passwordData: {
	oldPassword: string;
	password: string;
	confirmPassword: string;
}) => {
	const res = await apiFetch("/me/password", {
		method: "POST",
		body: JSON.stringify(passwordData),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const updateUserAvatar = async (avatar: File) => {
	const formData = new FormData();
	formData.append("avatar", avatar);

	const res = await apiFetch("/me/avatar", {
		method: "POST",
		body: formData,
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};

export const deleteUserAvatar = async () => {
	const res = await apiFetch("/me/avatar", {
		method: "DELETE",
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
