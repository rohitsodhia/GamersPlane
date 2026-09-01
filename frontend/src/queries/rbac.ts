import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

// Mirrors the backend hard locks in rbac_repository.py: role #1 and its member
// #1 can't be edited, re-granted, or removed via the API.
export const PROTECTED_ROLE_ID = 1;
export const PROTECTED_ROLE_MEMBER_ID = 1;

export type Effect = "allow" | "deny";

export type Permission = {
	value: string;
	label: string;
	// Allowed scope types for this verb: ["global"] means unscoped-only,
	// otherwise a single scope type such as ["forum"] or ["role"].
	scopes: string[];
};

export type RoleUser = {
	id: number;
	username: string;
};

export type Grant = {
	id: number;
	permission: { value: string; label: string };
	description: string | null;
	scope_type: string | null;
	scope_id: number | null;
	effect: Effect;
};

export type RoleDetail = {
	id: number;
	name: string;
	owner: RoleUser;
	users: RoleUser[];
	grants: Grant[];
};

export type Role = {
	id: number;
	name: string;
	owner: {
		id: number;
		username: string;
	};
	user_count: number;
	grant_count: number;
};

type GetRolesResponse = {
	roles: Role[];
};

export function rolesQueryOptions(nameFilter?: string, gameRoles = false) {
	return queryOptions({
		queryKey: ["rbac", "roles", nameFilter ?? null, gameRoles],
		queryFn: async (): Promise<Role[]> => {
			const params = new URLSearchParams();
			if (nameFilter) params.set("filter", nameFilter);
			if (gameRoles) params.set("game_roles", "true");
			const query = params.toString() ? `?${params}` : "";
			const res = await apiFetch(`/rbac/roles${query}`);
			if (!res.ok) throw new Error("Failed to fetch roles");
			return ((await res.json()) as GetRolesResponse).roles;
		},
		staleTime: 1000 * 30,
	});
}

export function roleQueryOptions(roleId: number) {
	return queryOptions({
		queryKey: ["rbac", "role", roleId],
		queryFn: async (): Promise<RoleDetail> => {
			const res = await apiFetch(`/rbac/roles/${roleId}`);
			if (!res.ok) throw new Error("Failed to fetch role");
			return (await res.json()) as RoleDetail;
		},
	});
}

export const permissionsQueryOptions = queryOptions({
	queryKey: ["rbac", "permissions"],
	queryFn: async (): Promise<Permission[]> => {
		const res = await apiFetch("/rbac/permissions");
		if (!res.ok) throw new Error("Failed to fetch permissions");
		return ((await res.json()) as { permissions: Permission[] }).permissions;
	},
	staleTime: 1000 * 60 * 5,
});

async function rbacMutate(path: string, method: string, body?: unknown) {
	const res = await apiFetch(path, {
		method,
		...(body === undefined ? {} : { body: JSON.stringify(body) }),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
}

export const createRole = async (body: {
	name: string;
	owner_id: number;
}): Promise<number> => {
	const res = await apiFetch("/rbac/roles", {
		method: "POST",
		body: JSON.stringify(body),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return ((await res.json()) as { id: number }).id;
};

export const updateRole = (
	roleId: number,
	body: { name?: string; owner_id?: number },
) => rbacMutate(`/rbac/roles/${roleId}`, "PATCH", body);

export const deleteRole = (roleId: number) =>
	rbacMutate(`/rbac/roles/${roleId}`, "DELETE");

export const createGrant = (
	roleId: number,
	body: {
		permission: string;
		scope_type: string | null;
		scope_id: number | null;
		effect: Effect;
	},
) => rbacMutate(`/rbac/roles/${roleId}/grants`, "POST", body);

export const updateGrant = (roleId: number, grantId: number, effect: Effect) =>
	rbacMutate(`/rbac/roles/${roleId}/grants/${grantId}`, "PATCH", { effect });

export const deleteGrant = (roleId: number, grantId: number) =>
	rbacMutate(`/rbac/roles/${roleId}/grants/${grantId}`, "DELETE");

export const addUserToRole = (roleId: number, userId: number) =>
	rbacMutate(`/rbac/roles/${roleId}/users`, "POST", { user_id: userId });

export const removeUserFromRole = (roleId: number, userId: number) =>
	rbacMutate(`/rbac/roles/${roleId}/users/${userId}`, "DELETE");
