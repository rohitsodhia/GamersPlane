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
