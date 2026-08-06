import { type QueryClient, queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

type PostSide = "l" | "r" | "c";

type MeResponse = {
	id: number;
	username: string;
	avatar: string;
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

const fetchMe = async (): Promise<MeResponse> => {
	const res = await apiFetch("/me");
	if (!res.ok) throw new Error("Failed to fetch current user");
	return res.json();
};

const fetchMeHeader = async (): Promise<MeHeaderResponse> => {
	const res = await apiFetch("/me/header");
	if (!res.ok) throw new Error("Failed to fetch header data");
	return res.json();
};

const fetchMeFull = async (): Promise<MeFullResponse> => {
	const res = await apiFetch("/me?full=true");
	if (!res.ok) throw new Error("Failed to fetch current user");
	const data: MeFullApiResponse = await res.json();
	return { ...data, joinDate: new Date(data.joinDate) };
};

export const meQueryOptions = queryOptions({
	queryKey: ["me"],
	queryFn: fetchMe,
	staleTime: 1000 * 60 * 5,
});

export const meHeaderQueryOptions = queryOptions({
	queryKey: ["me", "header"],
	queryFn: fetchMeHeader,
	staleTime: Number.POSITIVE_INFINITY,
});

// Nested under the "me" key so invalidating ["me"] invalidates this too.
export const meFullQueryOptions = queryOptions({
	queryKey: ["me", "full"],
	queryFn: fetchMeFull,
	staleTime: 1000 * 60 * 5,
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
