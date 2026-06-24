import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

type ReferralLink = {
	key: number;
	title: string;
	link: string;
	order: number;
};

type ReferralLinksResponse = {
	referralLinks: ReferralLink[];
};

export const referralLinksQueryOptions = queryOptions({
	queryKey: ["ReferralLinks"],
	queryFn: async (): Promise<ReferralLinksResponse> => {
		const res = await apiFetch("/referral_links/");
		if (!res.ok) throw new Error("Failed to fetch referral links data");
		return res.json();
	},
	staleTime: 1000 * 60 * 5,
});
