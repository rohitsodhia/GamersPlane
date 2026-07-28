import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

export type PMBox = "inbox" | "outbox";

type PMUser = {
	id: number;
	username: string;
	read: boolean;
};

export type PM = {
	id: number;
	recipient: PMUser;
	sender: PMUser;
	title: string;
	message: string;
	datestamp: string;
	reply_to_id: number | null;
};

type PMsListResponse = {
	pms: PM[];
	count: number;
	page: number;
	limit: number;
};

export function pmsQueryOptions(params: { box: PMBox; page: number }) {
	return queryOptions({
		queryKey: ["pms", params],
		queryFn: async (): Promise<PMsListResponse> => {
			const res = await apiFetch(`/pms?box=${params.box}&page=${params.page}`);
			if (!res.ok) throw new Error("Failed to fetch PMs");
			return res.json();
		},
		staleTime: 1000 * 30,
	});
}

export const deletePM = async (id: number) => {
	const res = await apiFetch(`/pms/${id}`, { method: "DELETE" });
	if (!res.ok) throw new Error("Failed to delete PM");
};
