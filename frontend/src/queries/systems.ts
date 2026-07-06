import { queryOptions, type UseSuspenseQueryOptions } from "@tanstack/react-query";
import { apiFetch } from "#/lib/api";

type Basic = {
	label: string;
	url: string;
};

type Publisher = {
	name: string;
	website: string | null;
};

type System = {
	id: string;
	name: string;
	sortName: string;
	publisher: Publisher | null;
	genres: string[];
	basics: Basic[];
	hasCharSheet: boolean;
	enabled: boolean;
};

type BasicSystem = {
	id: string;
	name: string;
	genres: string[];
	hasCharSheet: boolean;
};

export function systemsQueryOptions(params: {
	basic: true;
}): UseSuspenseQueryOptions<BasicSystem[]>;
export function systemsQueryOptions(params?: {
	basic?: false;
}): UseSuspenseQueryOptions<System[]>;
// biome-ignore lint/suspicious/noExplicitAny: overload implementation signature requires any to satisfy return type compatibility
export function systemsQueryOptions(params: { basic?: boolean } = {}): any {
	const search = params.basic ? "?basic=true" : "";
	return queryOptions({
		queryKey: ["systems", params],
		queryFn: async () => {
			const res = await apiFetch(`/systems/${search}`);
			if (!res.ok) throw new Error("Failed to fetch systems");
			return (await res.json()).systems;
		},
		staleTime: 1000 * 60 * 5,
	});
}
