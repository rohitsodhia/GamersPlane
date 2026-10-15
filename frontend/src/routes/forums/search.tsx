import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { DateTime } from "#/components/DateTime";
import ForumSearchForm from "#/components/ForumSearchForm";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	resultCountLabel,
	SEARCH_MAX_LENGTH,
	type SearchResult,
	searchPostsQueryOptions,
} from "#/queries/search";
import styles from "./search.module.css";

export const Route = createFileRoute("/forums/search")({
	validateSearch: z.object({
		// Coerced: the router parses `?q=123` into a number.
		q: z.coerce.string().optional(),
		game_id: z.number().optional(),
		page: z.number().optional(),
	}),
	component: RouteComponent,
});

function ResultItem({ result }: { result: SearchResult }) {
	return (
		<li className={styles["result"]}>
			<Link
				to="/forums/thread/$threadId"
				params={{ threadId: result.thread_id }}
				search={{ p: result.post_id }}
				className={styles["result-title"]}
			>
				{result.title}
			</Link>
			<div className={styles["result-meta"]}>
				in{" "}
				<Link to="/forums/{-$forumId}" params={{ forumId: result.forum_id }}>
					{result.forum_title}
				</Link>{" "}
				by{" "}
				<Link
					to="/user/$userId"
					params={{ userId: result.author.id }}
					className="username"
				>
					{result.author.username}
				</Link>{" "}
				on <DateTime value={result.published_at} />
			</div>
			<p className={styles["snippet"]}>
				{result.snippet.map((part, i) => {
					const Part = part.match ? "mark" : "span";
					// Parts are positional and never reordered.
					// biome-ignore lint/suspicious/noArrayIndexKey: static list
					return <Part key={i}>{part.text}</Part>;
				})}
			</p>
		</li>
	);
}

const errorMessage = (error: unknown) =>
	error instanceof ApiError && error.status === 422
		? `Search terms must be between 1 and ${SEARCH_MAX_LENGTH} characters.`
		: "Could not run the search. Please try again.";

function RouteComponent() {
	const { q = "", game_id: gameId, page = 1 } = Route.useSearch();
	const navigate = Route.useNavigate();
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const query = q.trim();

	const { data, isFetching, isError, error } = useQuery(
		searchPostsQueryOptions(query, gameId, page),
	);
	// A failed refetch leaves the last good data in place; don't show it as current.
	const shown = isError ? undefined : data;

	const pagination = (
		<div className={styles["pagination"]}>
			<Paginate numItems={shown?.count ?? 0} current={page} onPageChange={() => {}} />
		</div>
	);

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Search Posts
			</h1>
			<div style={{ marginInline: hbMargined.margin }}>
				{/* Keyed so a new URL query (e.g. from the header) resets the input. */}
				<ForumSearchForm
					key={`${query}-${gameId ?? ""}`}
					initialValue={query}
					gameId={gameId}
					placeholder="Search posts and thread titles"
					className={styles["form"]}
				/>
				{gameId !== undefined && (
					<p className={styles["scope-note"]}>
						Searching within one game's forums.{" "}
						<button
							type="button"
							className="link-btn"
							onClick={() =>
								navigate({
									search: (prev) => ({ ...prev, game_id: undefined, page: undefined }),
								})
							}
						>
							Search all forums
						</button>
					</p>
				)}

				{!query ? (
					<p className={styles["status"]}>Enter a search above to find posts.</p>
				) : isFetching ? (
					<LoadingSpinner />
				) : isError ? (
					<div className="banner error-banner">{errorMessage(error)}</div>
				) : shown && shown.results.length === 0 ? (
					<p className={styles["status"]}>No posts matched your search.</p>
				) : (
					shown && (
						<>
							<div className={styles["summary"]}>
								{resultCountLabel(shown.count, shown.count_capped)}
							</div>
							{pagination}
							<ol className={styles["results"]}>
								{shown.results.map((result) => (
									<ResultItem key={result.post_id} result={result} />
								))}
							</ol>
							{pagination}
						</>
					)
				)}
			</div>
		</div>
	);
}
