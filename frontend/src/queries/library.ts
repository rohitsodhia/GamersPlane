import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export const libraryQueryOptions = queryOptions({
	queryKey: ["library"],
	queryFn: async () => {
		const res = await apiFetch("/library");
		if (!res.ok) throw new Error("Failed to fetch library data");
		return res.json();
	},
	staleTime: 1000 * 60 * 5,
});

export const updateLibraryCount = (gameId: number, count: number) => {
	if (count === 0) {
		return apiFetch(`/library/${gameId}`, {
			method: "DELETE",
		}).then((res) => {
			if (!res.ok) throw new Error("Failed to remove from library");
		});
	} else {
		return apiFetch(`/library/${gameId}`, {
			method: "PUT",
			body: JSON.stringify({ count }),
		}).then((res) => {
			if (!res.ok) throw new Error("Failed to update library count");
		});
	}
};
