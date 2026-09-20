import { useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";
import { Autocomplete } from "#/components/Autocomplete";
import { DEBOUNCE_MS } from "#/lib/constants";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import styles from "./ListFilters.module.css";

/** Search params owned by ListFilters. Routes `.extend()` this with their own. */
export const listFiltersSearchSchema = z.object({
	search: z.string().optional(),
	systems: z.array(z.string()).optional(),
});

export type ListFilter = "search" | "systems";

type Props = {
	filters: ListFilter[];
	idPrefix?: string;
};

/**
 * Filter bar backed by URL search params. Must be rendered inside a route whose
 * `validateSearch` includes `listFiltersSearchSchema`; routes using the
 * "systems" filter should also `ensureQueryData(systemsQueryOptions({ basic: true }))`
 * in their loader.
 */
export function ListFilters({ filters, idPrefix = "list" }: Props) {
	return (
		<div className={styles["list-filters"]}>
			{filters.includes("search") && <SearchFilter />}
			{filters.includes("systems") && <SystemsFilter idPrefix={idPrefix} />}
		</div>
	);
}

function useFilterSearch() {
	const navigate = useNavigate();
	const urlSearch = useSearch({ strict: false }) as z.infer<
		typeof listFiltersSearchSchema
	>;
	const setFilters = (patch: Partial<z.infer<typeof listFiltersSearchSchema>>) =>
		navigate({
			to: ".",
			search: (prev) => ({ ...prev, ...patch, page: undefined }),
		});
	return { urlSearch, setFilters };
}

function SearchFilter() {
	const { urlSearch, setFilters } = useFilterSearch();
	const [searchInput, setSearchInput] = useState(urlSearch.search ?? "");

	// biome-ignore lint/correctness/useExhaustiveDependencies: setFilters is recreated each render and re-running on it would loop
	useEffect(() => {
		const timer = setTimeout(() => {
			setFilters({ search: searchInput || undefined });
		}, DEBOUNCE_MS);
		return () => clearTimeout(timer);
	}, [searchInput]);

	return (
		<input
			type="text"
			className={styles["title-search"]}
			placeholder="Search..."
			value={searchInput}
			onChange={(e) => setSearchInput(e.target.value)}
		/>
	);
}

function SystemsFilter({ idPrefix }: { idPrefix: string }) {
	const { urlSearch, setFilters } = useFilterSearch();
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));
	const [selectedSystemIds, setSelectedSystemIds] = useState(urlSearch.systems ?? []);

	const availableSystems = systems.filter(
		(system) => !selectedSystemIds.includes(system.id),
	);

	return (
		<div className={styles["system-filter"]}>
			<Autocomplete
				id={`${idPrefix}-system-filter-combo`}
				placeholder="Systems..."
				items={availableSystems}
				getId={(system: BasicSystem) => system.id}
				getLabel={(system: BasicSystem) => system.name}
				onAction={(id, { clear }) => {
					setSelectedSystemIds((prev) => [...prev, id]);
					clear();
				}}
			/>
			{selectedSystemIds.length > 0 && (
				<ul className={styles["systems-list"]}>
					{selectedSystemIds.map((id) => {
						const system = systems.find((s) => s.id === id);
						return (
							<li key={id}>
								<button
									type="button"
									onClick={() =>
										setSelectedSystemIds((prev) =>
											prev.filter((existing) => existing !== id),
										)
									}
								>
									{system?.name ?? id} <span>x</span>
								</button>
							</li>
						);
					})}
				</ul>
			)}
			<button
				type="button"
				className="skew-btn"
				onClick={() =>
					setFilters({
						systems: selectedSystemIds.length > 0 ? selectedSystemIds : undefined,
					})
				}
			>
				Apply
			</button>
		</div>
	);
}
