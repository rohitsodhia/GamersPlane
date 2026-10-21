import { useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { type ReactNode, useEffect, useState } from "react";
import { z } from "zod";
import { Autocomplete } from "#/components/Autocomplete";
import { Select } from "#/components/Select";
import { DEBOUNCE_MS } from "#/lib/constants";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import styles from "./ListFilters.module.css";

/** Search params owned by ListFilters. Routes `.extend()` this with their own. */
export const listFiltersSearchSchema = z.object({
	search: z.string().optional(),
	systems: z.array(z.string()).optional(),
});

/**
 * Search params for routes using the single-select "system" filter (one
 * `system_id`, as the API's `/my` lists take) instead of the multi-select
 * "systems" one. Routes `.extend()` this with their own.
 */
export const singleSystemFilterSearchSchema = z.object({
	search: z.string().optional(),
	system_id: z.string().optional(),
});

/** Search param for the "type" (PC / NPC) filter. Routes `.extend()` this with their own. */
export const typeFilterSearchSchema = z.object({
	type: z.enum(["pc", "npc"]).optional(),
});

type FilterSearch = z.infer<typeof listFiltersSearchSchema> &
	z.infer<typeof singleSystemFilterSearchSchema> &
	z.infer<typeof typeFilterSearchSchema>;

export type ListFilter = "search" | "systems" | "system" | "type";

const ALL_TYPES = "all";
const TYPE_OPTIONS: { id: string; name: string }[] = [
	{ id: ALL_TYPES, name: "All" },
	{ id: "pc", name: "PC" },
	{ id: "npc", name: "NPC" },
];

type Props = {
	filters: ListFilter[];
	idPrefix?: string;
	/** Route-specific filters (e.g. a type picker), rendered after the built-in ones. */
	children?: ReactNode;
};

/**
 * Filter bar backed by URL search params. Must be rendered inside a route whose
 * `validateSearch` includes `listFiltersSearchSchema` (or
 * `singleSystemFilterSearchSchema` for the "system" filter); routes using
 * "systems" or "system" should also
 * `ensureQueryData(systemsQueryOptions({ basic: true }))` in their loader.
 */
export function ListFilters({ filters, idPrefix = "list", children }: Props) {
	const { urlSearch, setFilters } = useFilterSearch();
	// Held here, not in SystemsFilter, so Apply can be the bar's last item.
	const [selectedSystemIds, setSelectedSystemIds] = useState(urlSearch.systems ?? []);

	return (
		<div className={styles["list-filters"]}>
			{filters.includes("search") && <SearchFilter />}
			{filters.includes("systems") && (
				<SystemsFilter
					idPrefix={idPrefix}
					selectedSystemIds={selectedSystemIds}
					onChange={setSelectedSystemIds}
				/>
			)}
			{filters.includes("system") && <SystemFilter idPrefix={idPrefix} />}
			{filters.includes("type") && <TypeFilter idPrefix={idPrefix} />}
			{children}
			{filters.includes("systems") && (
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
			)}
		</div>
	);
}

function useFilterSearch() {
	const navigate = useNavigate();
	const urlSearch = useSearch({ strict: false }) as FilterSearch;
	const setFilters = (patch: Partial<FilterSearch>) =>
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

function TypeFilter({ idPrefix }: { idPrefix: string }) {
	const { urlSearch, setFilters } = useFilterSearch();

	return (
		<Select
			id={`${idPrefix}-type-filter`}
			ariaLabel="Type"
			items={TYPE_OPTIONS}
			getId={(option) => option.id}
			getLabel={(option) => option.name}
			selectedId={urlSearch.type ?? ALL_TYPES}
			onChange={(id) =>
				setFilters({ type: id === ALL_TYPES ? undefined : (id as "pc" | "npc") })
			}
		/>
	);
}

function SystemFilter({ idPrefix }: { idPrefix: string }) {
	const { setFilters } = useFilterSearch();
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));

	return (
		<Autocomplete
			id={`${idPrefix}-system-filter`}
			items={systems}
			getId={(system: BasicSystem) => system.id}
			getLabel={(system: BasicSystem) => system.name}
			placeholder="System"
			onAction={(id) => setFilters({ system_id: id })}
			onClear={() => setFilters({ system_id: undefined })}
		/>
	);
}

function SystemsFilter({
	idPrefix,
	selectedSystemIds,
	onChange: setSelectedSystemIds,
}: {
	idPrefix: string;
	selectedSystemIds: string[];
	onChange: (update: (prev: string[]) => string[]) => void;
}) {
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));

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
		</div>
	);
}
