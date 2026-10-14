import { queryOptions } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/core";
import { ApiError, apiFetch } from "#/lib/api";

export type FaqCategorySlug = "getting-started" | "characters" | "games" | "tools";

export type Faq = {
	id: number;
	category: FaqCategorySlug;
	question: string;
	answer: JSONContent;
	order: number;
};

export type FaqCategory = {
	category: FaqCategorySlug;
	label: string;
	faqs: Faq[];
};

type FaqsResponse = { categories: FaqCategory[] };

export type FaqInput = {
	category: FaqCategorySlug;
	question: string;
	answer: JSONContent;
};

export const faqsQueryOptions = queryOptions({
	queryKey: ["faqs"],
	queryFn: async (): Promise<FaqsResponse> => {
		const res = await apiFetch("/faqs");
		if (!res.ok) throw new Error("Failed to fetch FAQs");
		return res.json();
	},
	staleTime: 1000 * 60 * 5,
});

const throwApiError = async (res: Response): Promise<never> => {
	const errors = await res
		.json()
		.then((body) => body.errors ?? [])
		.catch(() => []);
	throw new ApiError(res.status, errors);
};

export const createFaq = async (data: FaqInput): Promise<Faq> => {
	const res = await apiFetch("/faqs", { method: "POST", body: JSON.stringify(data) });
	if (!res.ok) return throwApiError(res);
	return res.json();
};

export const updateFaq = async ({
	id,
	...data
}: FaqInput & { id: number }): Promise<Faq> => {
	const res = await apiFetch(`/faqs/${id}`, {
		method: "PUT",
		body: JSON.stringify(data),
	});
	if (!res.ok) return throwApiError(res);
	return res.json();
};

export const deleteFaq = async (id: number): Promise<void> => {
	const res = await apiFetch(`/faqs/${id}`, { method: "DELETE" });
	if (!res.ok) return throwApiError(res);
};

export const moveFaq = async ({
	id,
	direction,
}: {
	id: number;
	direction: "up" | "down";
}): Promise<void> => {
	const res = await apiFetch(`/faqs/${id}/move`, {
		method: "POST",
		body: JSON.stringify({ direction }),
	});
	if (!res.ok) return throwApiError(res);
};

/** Turns a failed FAQ mutation into a message that's safe to show the user. */
export const faqErrorMessage = (error: unknown): string => {
	if (error instanceof ApiError) {
		if (error.status === 403) return "You don't have permission to manage FAQs.";
		if (error.status === 404) return "That FAQ no longer exists. Reload the page.";
		if (error.status === 422) {
			const details = error.errors.map((e) => e.detail).filter(Boolean);
			if (details.length > 0) return details.join(" ");
			return "The FAQ couldn't be saved. Check the fields and try again.";
		}
	}
	return "Something went wrong. Please try again.";
};
