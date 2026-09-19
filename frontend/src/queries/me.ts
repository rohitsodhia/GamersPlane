import { type QueryClient, queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";
import { useAuthStore } from "#/stores/auth";

export type PostSide = "r" | "l" | "c";

export type MeResponse = {
	id: number;
	username: string;
	avatar: string;
	acp: boolean;
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
	joinDate: string;
	pronouns: string | null;
	birthday: string | null;
	showAge: boolean | null;
	location: string | null;
	pmMail: boolean | null;
	newGameMail: boolean | null;
	gmMail: boolean | null;
	postSide: PostSide;
	lookingForAGame: boolean | null;
	games: string | null;
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
	postSide?: PostSide;
	lookingForAGame?: boolean;
	games?: string;
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
