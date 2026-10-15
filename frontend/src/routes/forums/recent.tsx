import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	RECENT_SCOPE_LABELS,
	RECENT_SCOPES,
	recentThreadsQueryOptions,
	type ThreadWithForum,
} from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import { ThreadList } from "./-thread-list";
import styles from "./recent.module.css";

export const Route = createFileRoute("/forums/recent")({
	validateSearch: z.object({
		scope: z.enum(RECENT_SCOPES).optional(),
		page: z.number().optional(),
	}),
	// Unread posts are per user; guests are sent to log in and back.
	beforeLoad: ({ search, location }) => {
		if (search.scope === "unread") requireAuth({ location });
	},
	component: RouteComponent,
});

// Its own component so the margin hook belongs to the one that renders the list
// header: the header only mounts once the threads have loaded, and the hook measures
// when its component mounts (it would miss a header that appears later).
function RecentThreads({
	threads,
	count,
	page,
	margin,
}: {
	threads: ThreadWithForum[];
	count: number;
	page: number;
	margin: number;
}) {
	const hbMarginedList = useHbMargined<HTMLDivElement>();

	return (
		<>
			<div className={styles["pagination"]} style={{ marginInline: margin }}>
				<Paginate numItems={count} current={page} onPageChange={() => {}} />
			</div>
			<ThreadList
				threads={threads}
				headerRef={hbMarginedList.ref}
				margin={hbMarginedList.margin}
			/>
			<div className={styles["pagination"]} style={{ marginInline: margin }}>
				<Paginate numItems={count} current={page} onPageChange={() => {}} />
			</div>
		</>
	);
}

function RouteComponent() {
	const { scope = "latest", page = 1 } = Route.useSearch();
	const loggedIn = useAuthStore((state) => !!state.token);
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	const { data, isPending, isError } = useQuery(recentThreadsQueryOptions(scope, page));

	const scopes = RECENT_SCOPES.filter((s) => s !== "unread" || loggedIn);

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{RECENT_SCOPE_LABELS[scope]}
			</h1>
			<div style={{ marginInline: hbMargined.margin }}>
				<nav className={styles["scopes"]} aria-label="Recent post views">
					{scopes.map((s) => (
						<Link
							key={s}
							to="/forums/recent"
							search={{ scope: s }}
							className={styles["scope"]}
							data-active={s === scope || undefined}
							aria-current={s === scope ? "page" : undefined}
						>
							{RECENT_SCOPE_LABELS[s]}
						</Link>
					))}
				</nav>
				<p className={styles["note"]}>Threads with a post in the last week.</p>
			</div>

			{isPending ? (
				<LoadingSpinner />
			) : isError ? (
				<div
					className="banner error-banner"
					style={{ marginInline: hbMargined.margin }}
				>
					Could not load threads. Please try again.
				</div>
			) : (
				<RecentThreads
					threads={data.threads}
					count={data.count}
					page={page}
					margin={hbMargined.margin}
				/>
			)}
		</div>
	);
}
