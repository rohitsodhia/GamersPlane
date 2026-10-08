import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";
import { forumMutate } from "#/queries/forums";

export type PermissionEffect = "allow" | "deny";

export type PermissionVerb = {
	value: string;
	label: string;
};

export type PermissionRole = {
	id: number;
	name: string;
	kind: "player" | "custom" | "registered" | "guest" | "site";
	// Only this forum's own grants; a missing verb inherits.
	grants: Record<string, PermissionEffect>;
	// What the role alone resolves to from the parent forums.
	inherited: Record<string, boolean>;
};

export type ForumPermissions = {
	can_grant_moderate: boolean;
	verbs: PermissionVerb[];
	roles: PermissionRole[];
};

export type RoleMember = {
	id: number;
	username: string;
};

export type GameRole = {
	id: number;
	name: string;
	kind: "player" | "custom";
	members: RoleMember[];
};

export type GameRoles = {
	roles: GameRole[];
	players: RoleMember[];
};

export type SiteRole = {
	id: number;
	name: string;
};

export function forumPermissionsQueryOptions(forumId: number) {
	return queryOptions({
		queryKey: ["forums", forumId, "permissions"],
		queryFn: async (): Promise<ForumPermissions> => {
			const res = await apiFetch(`/forums/${forumId}/permissions`);
			if (!res.ok) throw new Error("Failed to fetch forum permissions");
			return res.json();
		},
		staleTime: 1000 * 60,
	});
}

export const setForumPermissions = (
	forumId: number,
	roles: { role_id: number; grants: Record<string, PermissionEffect> }[],
) => forumMutate(`/forums/${forumId}/permissions`, "PUT", { roles });

export async function searchPermissionRoles(
	forumId: number,
	filter: string,
): Promise<SiteRole[]> {
	const res = await apiFetch(
		`/forums/${forumId}/permissions/roles?filter=${encodeURIComponent(filter)}`,
	);
	if (!res.ok) throw new Error("Failed to search roles");
	return (await res.json()).roles;
}

export function gameRolesQueryOptions(forumId: number) {
	return queryOptions({
		queryKey: ["forums", forumId, "roles"],
		queryFn: async (): Promise<GameRoles> => {
			const res = await apiFetch(`/forums/${forumId}/roles`);
			if (!res.ok) throw new Error("Failed to fetch game roles");
			return res.json();
		},
		staleTime: 1000 * 60,
	});
}

export const createGameRole = async (
	forumId: number,
	name: string,
): Promise<number> => {
	const res = await forumMutate(`/forums/${forumId}/roles`, "POST", { name });
	return (await res.json()).id;
};

export const renameGameRole = (forumId: number, roleId: number, name: string) =>
	forumMutate(`/forums/${forumId}/roles/${roleId}`, "PATCH", { name });

export const deleteGameRole = (forumId: number, roleId: number) =>
	forumMutate(`/forums/${forumId}/roles/${roleId}`, "DELETE");

// Replaces the whole membership.
export const setGameRoleMembers = (
	forumId: number,
	roleId: number,
	userIds: number[],
) =>
	forumMutate(`/forums/${forumId}/roles/${roleId}/members`, "PUT", {
		user_ids: userIds,
	});
