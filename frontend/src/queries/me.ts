import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

type MeResponse = {
	id: number;
	username: string;
	avatar: string;
};

export const meQueryOptions = queryOptions({
	queryKey: ["me"],
	queryFn: async (): Promise<MeResponse> => {
		const res = await apiFetch("/auth/me");
		if (!res.ok) throw new Error("Failed to fetch current user");
		return res.json();
	},
	staleTime: 1000 * 60 * 5,
});
