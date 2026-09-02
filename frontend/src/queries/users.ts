import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

export type SearchUser = {
	id: number;
	username: string;
};

type ActiveGame = {
	id: number;
	name: string;
	isGM: boolean;
	system: string;
	forumId: number | null;
};

type System = {
	id: string;
	name: string;
};

type SystemCount = {
	system: System;
	count: number;
};

type SystemsCount = {
	count: number;
	systems: SystemCount[];
};

export type UserProfile = {
	id: number;
	username: string;
	avatar: string;
	joinDate: string;
	lastActivity: string | null;
	banned: string | null;
	pronouns: string | null;
	showAge: boolean;
	age: string | null;
	location: string | null;
	postCount: number;
	communityPostCount: number;
	gamePostCount: number;
	activeGames: ActiveGame[];
	characters: SystemsCount;
	gmStats: SystemsCount;
};

export function userQueryOptions(userId: number) {
	return queryOptions({
		queryKey: ["users", userId],
		queryFn: async (): Promise<UserProfile> => {
			const res = await apiFetch(`/users/${userId}`);
			if (!res.ok) throw new Error("Failed to fetch user");
			const { user } = await res.json();
			return user;
		},
	});
}

export type UserListRow = {
	id: number;
	username: string;
	avatar: string;
	joinDate: string;
	lastActivity?: string | null;
	activated: boolean;
	banned?: string | null;
	// "full" fields, only present when the list is requested with full=true
	pronouns?: string | null;
	showAge?: boolean;
	age?: string | null;
	location?: string | null;
};

export type UsersListResponse = {
	users: UserListRow[];
	count: number;
	page: number;
};

export function usersListQueryOptions(params: {
	page: number;
	prefix?: string;
	banned?: boolean;
	full?: boolean;
}) {
	return queryOptions({
		queryKey: ["users", "list", params],
		queryFn: async (): Promise<UsersListResponse> => {
			const search = new URLSearchParams({ page: String(params.page) });
			if (params.prefix) search.set("prefix", params.prefix);
			if (params.banned !== undefined) search.set("banned", String(params.banned));
			if (params.full) search.set("full", "true");
			const res = await apiFetch(`/users?${search}`);
			if (!res.ok) throw new Error("Failed to fetch users");
			return res.json();
		},
		staleTime: 1000 * 30,
	});
}

// TODO: this endpoint doesn't exist yet — mock the request/latency for now so the
// ACP button exercises a real pending/settled cycle. Swap the body for an
// `apiFetch(...)` call once the API lands.
const mockApiCall = (label: string, userId: number) =>
	new Promise<void>((resolve) => {
		console.info(`[mock] ${label} for user ${userId}`);
		setTimeout(resolve, 600);
	});

export const sendActivationLink = (userId: number): Promise<void> =>
	mockApiCall("send activation link", userId);

// Toggles the ban: bans an unbanned user, unbans a banned one.
export const toggleUserBan = async (userId: number): Promise<void> => {
	const res = await apiFetch(`/users/${userId}/ban`, { method: "PATCH" });
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
};

export const searchUsers = async (username: string): Promise<SearchUser[]> => {
	const res = await apiFetch(
		`/users/autocomplete?username=${encodeURIComponent(username)}`,
	);
	if (!res.ok) {
		throw new Error("Failed to search users");
	}
	return ((await res.json()) as { users: SearchUser[] }).users;
};

export const searchUserByUsername = async (
	username: string,
): Promise<SearchUser | null> => {
	const res = await apiFetch(`/users/search?username=${encodeURIComponent(username)}`);
	if (res.status === 404) {
		return null;
	}
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	const { user } = await res.json();
	return user;
};

export const searchUserById = async (id: number): Promise<SearchUser | null> => {
	const res = await apiFetch(`/users/search?id=${id}`);
	if (res.status === 404) {
		return null;
	}
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	const { user } = await res.json();
	return user;
};

export function searchUserByIdQueryOptions(id: number) {
	return queryOptions({
		queryKey: ["users", "search", { id }],
		queryFn: () => searchUserById(id),
	});
}
