import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { ListFilters, listFiltersSearchSchema } from "#/components/ListFilters";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { libraryQueryOptions } from "#/queries/character";
import { systemsQueryOptions } from "#/queries/systems";
import styles from "./library.module.css";

export const Route = createFileRoute("/characters/library")({
	beforeLoad: requireAuth,
	validateSearch: listFiltersSearchSchema.extend({
		page: z.number().optional(),
	}),
	// Only the systems list is loaded here (no loaderDeps on the filters) so
	// filter/page changes don't re-run the loader and flash the pending
	// component; LibraryResults' useQuery fetches them client-side instead.
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Character Library
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<ListFilters filters={["search", "systems"]} idPrefix="characters" />
				<LibraryResults />
			</div>
		</div>
	);
}

function LibraryResults() {
	const { page: urlPage, search, systems } = Route.useSearch();
	const page = urlPage ?? 1;

	const { data, isFetching, isError } = useQuery(
		libraryQueryOptions({ search, systems, page }),
	);
	const characters = data?.characters ?? [];

	return (
		<div className={styles["library-results"]}>
			{isFetching ? (
				<LoadingSpinner />
			) : isError ? (
				<div className="banner error-banner">
					Could not load the library. Please try again.
				</div>
			) : characters.length > 0 ? (
				<ul className={styles["library-list"]}>
					{characters.map((character) => (
						<li key={character.id}>
							<div className={styles.label}>
								<Link
									to="/characters/$characterId"
									params={{ characterId: character.id }}
								>
									{character.label}
								</Link>
							</div>
							<div className={styles["system-name"]}>{character.system.name}</div>
							<div className={styles.owner}>
								<Link
									to="/user/$userId"
									params={{ userId: character.user.id }}
									className="username"
								>
									{character.user.username}
								</Link>
							</div>
						</li>
					))}
				</ul>
			) : (
				<div className={styles.notice}>No characters match your filters.</div>
			)}

			<div className={styles["library-pagination"]}>
				<Paginate numItems={data?.total ?? 0} current={page} onPageChange={() => {}} />
			</div>
		</div>
	);
}
