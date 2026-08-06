import { ApiError, apiFetch } from "#/lib/api";

export type SearchUser = {
	id: number;
	username: string;
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
