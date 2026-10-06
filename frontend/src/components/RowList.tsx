import type { CSSProperties, ReactNode } from "react";
import styles from "./RowList.module.css";

type RowListProps = {
	/** CSS grid track list shared by every row, e.g. "1fr auto auto". */
	columns: string;
	children: ReactNode;
};

/** Grid list whose rows share column widths. Children are `RowListItem`s. */
export function RowList({ columns, children }: RowListProps) {
	return (
		<ul
			className={styles["row-list"]}
			style={{ "--row-list-columns": columns } as CSSProperties}
		>
			{children}
		</ul>
	);
}

type RowListItemProps = {
	/** Italicises rows the user favorited rather than owns. */
	favorited?: boolean;
	children: ReactNode;
};

/**
 * One row: a cell per column. A cell with the class `links` (see
 * `rowLinksClassName`) is right-aligned and not text-trimmed.
 */
export function RowListItem({ favorited, children }: RowListItemProps) {
	return (
		<li className={`${styles["row"]}${favorited ? ` ${styles["favorited"]}` : ""}`}>
			{children}
		</li>
	);
}

/** Class for the trailing actions cell of a row. */
export const rowLinksClassName = styles["links"];
