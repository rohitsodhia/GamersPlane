import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";
import { Checkbox } from "#/components/Checkbox";
import { InactiveMarker } from "#/components/InactiveMarker";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import RAIcon from "#/components/RAIcon";
import { Select } from "#/components/Select";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { DEBOUNCE_MS } from "#/lib/constants";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	GAMERS_PER_PAGE,
	type Gamer,
	type GamerSort,
	gamersQueryOptions,
} from "#/queries/gamers";
import styles from "./gamers.module.css";

const searchSchema = z.object({
	search: z.string().optional(),
	lfg: z.boolean().optional(),
	inactive: z.boolean().optional(),
	sort: z.enum(["name", "newest", "oldest"]).optional(),
	page: z.number().optional(),
});
type GamersSearch = z.infer<typeof searchSchema>;

const SORT_OPTIONS: { id: GamerSort; name: string }[] = [
	{ id: "name", name: "Name" },
	{ id: "newest", name: "Newest" },
	{ id: "oldest", name: "Oldest" },
];

const queryParams = (search: GamersSearch) => ({
	search: search.search,
	lfg: search.lfg,
	includeInactive: search.inactive,
	sort: search.sort ?? "name",
	page: search.page ?? 1,
});

export const Route = createFileRoute("/gamers")({
	beforeLoad: requireAuth,
	validateSearch: searchSchema,
	// No loaderDeps: filters re-fetch through the component's own useQuery so a
	// change doesn't hand rendering to the full-page pending component.
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(
				gamersQueryOptions(queryParams(location.search as GamersSearch)),
			),
			location,
		),
	component: RouteComponent,
});

const DEFAULT_AVATAR_FILE = "avatar.png";

function GamerCard({ gamer }: { gamer: Gamer }) {
	return (
		<li className={styles["card"]}>
			{gamer.lfg && (
				<RAIcon
					className={`ra-health ${styles["lfg-icon"]}`}
					title="Looking for a game"
				/>
			)}
			{gamer.online && (
				<span
					className={styles["online-dot"]}
					role="img"
					aria-label="Online now"
					title="Online now"
				/>
			)}
			<Link to="/user/$userId" params={{ userId: gamer.id }}>
				<img
					className="avatar"
					src={gamer.avatar}
					alt={`${gamer.username} Avatar`}
					loading="lazy"
					onError={(event) => {
						const img = event.currentTarget;
						const fallback = img.src.replace(/[^/]+$/, DEFAULT_AVATAR_FILE);
						// Guard so a missing default doesn't loop.
						if (img.src !== fallback) img.src = fallback;
					}}
				/>
			</Link>
			<div className={styles["card-info"]}>
				<Link to="/user/$userId" params={{ userId: gamer.id }}>
					{gamer.username}
				</Link>
				<InactiveMarker lastActivity={gamer.lastActivity} />
			</div>
		</li>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	const params = queryParams(search);

	const [searchInput, setSearchInput] = useState(search.search ?? "");

	// Debounce typing into the URL; any filter change drops back to page 1.
	useEffect(() => {
		const next = searchInput.trim() || undefined;
		if (next === search.search) return;
		const timer = setTimeout(() => {
			navigate({ search: (prev) => ({ ...prev, search: next, page: undefined }) });
		}, DEBOUNCE_MS);
		return () => clearTimeout(timer);
	}, [searchInput, search.search, navigate]);

	const setFilter = (patch: Partial<GamersSearch>) =>
		navigate({ search: (prev) => ({ ...prev, ...patch, page: undefined }) });

	const { data, isFetching, isError } = useQuery(gamersQueryOptions(params));
	// A failed refetch leaves the last good data in place; don't show it as current.
	const shown = isError ? undefined : data;
	const gamers = shown?.gamers ?? [];

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				GP's Gamers
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<div className={styles["filters"]}>
					<input
						type="text"
						className={styles["search"]}
						placeholder="Search gamers..."
						aria-label="Search gamers"
						value={searchInput}
						onChange={(e) => setSearchInput(e.target.value)}
					/>
					<div className={styles["check"]}>
						<Checkbox
							id="gamers-lfg"
							checked={search.lfg === true}
							onChange={(checked) => setFilter({ lfg: checked || undefined })}
						/>
						<label htmlFor="gamers-lfg">Looking for a game</label>
					</div>
					<div className={styles["check"]}>
						<Checkbox
							id="gamers-inactive"
							checked={search.inactive === true}
							onChange={(checked) => setFilter({ inactive: checked || undefined })}
						/>
						<label htmlFor="gamers-inactive">Show inactive users</label>
					</div>
					<Select
						id="gamers-sort"
						ariaLabel="Sort by"
						items={SORT_OPTIONS}
						getId={(option) => option.id}
						getLabel={(option) => option.name}
						selectedId={params.sort}
						onChange={(id) =>
							setFilter({ sort: id === "name" ? undefined : (id as GamerSort) })
						}
					/>
				</div>

				<Paginate
					numItems={shown?.total ?? 0}
					itemsPerPage={GAMERS_PER_PAGE}
					current={params.page}
					onPageChange={() => {}}
				/>

				<div className={styles["results"]}>
					{isFetching ? (
						<LoadingSpinner />
					) : isError ? (
						<div className="banner error-banner">
							Could not load gamers. Please try again.
						</div>
					) : gamers.length > 0 ? (
						<ul className={styles["grid"]}>
							{gamers.map((gamer) => (
								<GamerCard key={gamer.id} gamer={gamer} />
							))}
						</ul>
					) : (
						<div className={styles["no-results"]}>No gamers match your filters.</div>
					)}
				</div>

				<Paginate
					numItems={shown?.total ?? 0}
					itemsPerPage={GAMERS_PER_PAGE}
					current={params.page}
					onPageChange={() => {}}
				/>
			</div>
		</div>
	);
}
