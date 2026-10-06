import type { ReactNode } from "react";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import styles from "./ListResults.module.css";

type Props = {
	isFetching: boolean;
	isError: boolean;
	/** Whether the current page has any rows to render. */
	hasResults: boolean;
	total: number;
	page: number;
	errorMessage: string;
	emptyMessage: string;
	children: ReactNode;
};

/**
 * The results area of a paginated list: a spinner while fetching, an error
 * banner, the rows, or an empty message, plus pagination underneath.
 *
 * Pair it with a plain `useQuery` + `keepPreviousData` (not a suspense query)
 * so a refetch flips `isFetching` instead of handing rendering to the
 * router's full-page pending component.
 */
export function ListResults({
	isFetching,
	isError,
	hasResults,
	total,
	page,
	errorMessage,
	emptyMessage,
	children,
}: Props) {
	return (
		<>
			<div className={styles["results"]}>
				{isFetching ? (
					<LoadingSpinner />
				) : isError ? (
					<div className="banner error-banner">{errorMessage}</div>
				) : hasResults ? (
					children
				) : (
					<div className={styles["no-results"]}>{emptyMessage}</div>
				)}
			</div>

			<Paginate numItems={total} current={page} onPageChange={() => {}} />
		</>
	);
}
