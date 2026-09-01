import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";
import { Autocomplete } from "#/components/Autocomplete";
import { DEBOUNCE_MS } from "#/lib/constants";
import { useHbMargined } from "#/lib/use-hb-margined";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import styles from "./list.module.css";

export const Route = createFileRoute("/games/list")({
	validateSearch: z.object({
		page: z.number().optional(),
		search: z.string().optional(),
		systems: z.array(z.string()).optional(),
	}),
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
	},
	component: RouteComponent,
});

function RouteComponent() {
	const navigate = useNavigate({ from: Route.fullPath });
	const { search: urlSearch, systems: urlSystems } = Route.useSearch();
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));

	const [searchInput, setSearchInput] = useState(urlSearch ?? "");
	const [selectedSystemIds, setSelectedSystemIds] = useState(urlSystems ?? []);

	// biome-ignore lint/correctness/useExhaustiveDependencies: navigate is stable and re-running on it would loop
	useEffect(() => {
		const timer = setTimeout(() => {
			navigate({
				search: (prev) => ({
					...prev,
					search: searchInput || undefined,
					page: undefined,
				}),
			});
		}, DEBOUNCE_MS);
		return () => clearTimeout(timer);
	}, [searchInput]);

	const availableSystems = systems.filter(
		(system) => !selectedSystemIds.includes(system.id),
	);

	const applySystemFilter = () => {
		navigate({
			search: (prev) => ({
				...prev,
				systems: selectedSystemIds.length > 0 ? selectedSystemIds : undefined,
				page: undefined,
			}),
		});
	};

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				<i className="ra ra-d6" /> Browse Games
			</h1>

			<div style={{ marginInline: hbMargined.margin }}>
				<div className={styles["games-filters"]}>
					<input
						type="text"
						className={styles["title-search"]}
						placeholder="Search..."
						value={searchInput}
						onChange={(e) => setSearchInput(e.target.value)}
					/>

					<div className={styles["system-filter"]}>
						<Autocomplete
							id="games-system-filter-combo"
							items={availableSystems}
							getId={(system: BasicSystem) => system.id}
							getLabel={(system: BasicSystem) => system.name}
							onAction={(id) => setSelectedSystemIds((prev) => [...prev, id])}
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
						<button type="button" className="skew-btn" onClick={applySystemFilter}>
							Apply
						</button>
					</div>
				</div>

				<Outlet />
			</div>
		</div>
	);
}
