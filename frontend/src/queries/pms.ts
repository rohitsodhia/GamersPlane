import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";

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
	message: JSONContent;
	datestamp: string;
	reply_to_id: number | null;
};

export type PMDetail = PM & {
	history: PM[];
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

export function pmQueryOptions(id: number) {
	return queryOptions({
		queryKey: ["pms", id],
		queryFn: async (): Promise<PMDetail> => {
			const res = await apiFetch(`/pms/${id}`);
			if (!res.ok) throw new Error("Failed to fetch PM");
			const { pm } = await res.json();
			return pm;
		},
	});
}

export const deletePM = async (id: number) => {
	const res = await apiFetch(`/pms/${id}`, { method: "DELETE" });
	if (!res.ok) throw new Error("Failed to delete PM");
};

export const sendPM = async (data: {
	username: string;
	title: string;
	message: JSONContent;
	reply_to_id?: number;
}) => {
	const res = await apiFetch("/pms", {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
};
