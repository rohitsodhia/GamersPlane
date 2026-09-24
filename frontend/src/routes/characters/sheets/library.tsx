import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { ListFilters, listFiltersSearchSchema } from "#/components/ListFilters";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	characterSheetLibraryQueryOptions,
	type GetCharacterSheetLibraryResponse,
	toggleCharacterSheetFavorite,
} from "#/queries/characterSheet";
import { systemsQueryOptions } from "#/queries/systems";
import styles from "../library.module.css";

export const Route = createFileRoute("/characters/sheets/library")({
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
				Character Sheet Library
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<ListFilters filters={["search", "systems"]} idPrefix="sheets" />
				<LibraryResults />
			</div>
		</div>
	);
}

function LibraryResults() {
	const { page: urlPage, search, systems } = Route.useSearch();
	const page = urlPage ?? 1;

	const { data, isFetching, isError } = useQuery(
		characterSheetLibraryQueryOptions({ search, systems, page }),
	);
	const charSheets = data?.char_sheets ?? [];

	// Write the server's answer into the cached lists in place rather than
	// invalidating: a refetch sets isFetching, which would swap the list for
	// the spinner.
	const queryClient = useQueryClient();
	const toggleFavoriteMutation = useMutation({
		mutationFn: toggleCharacterSheetFavorite,
		onSuccess: ({ favorited }, sheetId) => {
			queryClient.setQueriesData<GetCharacterSheetLibraryResponse>(
				{ queryKey: ["characterSheets", "library"] },
				(old) =>
					old && {
						...old,
						char_sheets: old.char_sheets.map((sheet) =>
							sheet.id === sheetId ? { ...sheet, favorited } : sheet,
						),
					},
			);
		},
	});

	return (
		<div className={styles["library-results"]}>
			{isFetching ? (
				<LoadingSpinner />
			) : isError ? (
				<div className="banner error-banner">
					Could not load the library. Please try again.
				</div>
			) : charSheets.length > 0 ? (
				<ul className={styles["library-list"]}>
					{charSheets.map((sheet) => (
						<li key={sheet.id}>
							<div className={styles.label}>
								<Link
									to="/characters/sheets/$sheetId"
									params={{ sheetId: sheet.id }}
									search={{ from: "library" }}
								>
									{sheet.name}
								</Link>
							</div>
							<div className={styles["system-name"]}>{sheet.system.name}</div>
							<div className={styles.owner}>
								<Link
									to="/user/$userId"
									params={{ userId: sheet.creator.id }}
									className="username"
								>
									{sheet.creator.username}
								</Link>
							</div>
							<div className={styles.favorite}>
								<button
									type="button"
									disabled={
										toggleFavoriteMutation.isPending &&
										toggleFavoriteMutation.variables === sheet.id
									}
									onClick={() => toggleFavoriteMutation.mutate(sheet.id)}
								>
									{sheet.favorited ? (
										<img src="/images/icons/bookmark_on.png" alt="Favorited" />
									) : (
										<img src="/images/icons/bookmark_off.png" alt="Favorite" />
									)}
								</button>
							</div>
						</li>
					))}
				</ul>
			) : (
				<div className={styles.notice}>No character sheets match your filters.</div>
			)}

			<div className={styles["library-pagination"]}>
				<Paginate numItems={data?.total ?? 0} current={page} onPageChange={() => {}} />
			</div>
		</div>
	);
}
