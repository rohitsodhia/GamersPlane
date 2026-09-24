import type { QueryClient, QueryKey } from "@tanstack/react-query";

/**
 * Drop an item from every cached paginated list under `queryKey`, and
 * decrement its `total`. Done in place rather than by invalidating: a refetch
 * sets isFetching, which would swap the whole list for the spinner.
 *
 * `itemsKey` names the array field holding the rows (e.g. "characters").
 */
export function removeFromCachedLists<K extends string>(
	queryClient: QueryClient,
	queryKey: QueryKey,
	itemsKey: K,
	id: number,
) {
	queryClient.setQueriesData<Record<K, { id: number }[]> & { total: number }>(
		{ queryKey },
		(old) =>
			old && {
				...old,
				[itemsKey]: old[itemsKey].filter((item) => item.id !== id),
				total: Math.max(0, old.total - 1),
			},
	);
}
