import clsx from "clsx";
import type { CSSProperties, ReactNode } from "react";
import { CollapsibleScopeProvider } from "./collapsible-scope";
import { KeyedScopeProvider } from "./sheet-values";
import type { SheetElement } from "./types";

/** One data row, already normalised from either authoring form by the renderer. */
export interface GridRow {
	/** Sub-scope key this row's fields nest under (`stats.str.*`). */
	key: string;
	/** Cells in column order; cell 0 is normally the row label. */
	cells: SheetElement[];
	/** Extra allowlisted class for this one row (explicit form's `grid_row` class). */
	rowClass?: string;
}

/** The optional header row, normalised from `header` / `grid_header`. */
export interface GridHeader {
	cells: SheetElement[];
}

interface GridProps {
	name: string;
	/**
	 * Pre-validated `grid-template-columns` value (see `validateColumns`), or
	 * undefined for none — then the tracks come from a helper class on the grid
	 * or the `.char-sheet-grid` stylesheet fallback.
	 */
	gridTemplateColumns?: string;
	/** Extra allowlisted class applied to every row wrapper. */
	rowClass?: string;
	className?: string;
	style?: CSSProperties;
	header?: GridHeader;
	rows: GridRow[];
	/**
	 * Renders one cell of a data row. The renderer owns this so recursion, keying
	 * and unknown-type handling stay in one place; Grid only decides the row set
	 * and the layout.
	 */
	renderCell: (cell: SheetElement, rowKey: string, cellIndex: number) => ReactNode;
	/** Renders one header cell. Same rationale as `renderCell`. */
	renderHeaderCell: (cell: SheetElement, index: number) => ReactNode;
}

/**
 * A fixed-layout table. Each row renders into its own string-keyed sub-scope
 * (via <KeyedScopeProvider>), so the value doc nests as
 * `name: { <key>: { <field>: value, … } }`.
 *
 * Laid out as a CSS grid: `gridTemplateColumns` (or a helper class / the
 * stylesheet fallback) sets the tracks on the container, and the header plus
 * each row is a subgrid row (see `char-sheet.css`) so cells line up
 * across rows while every row stays its own styleable box. A header cell may
 * carry `col` to pin it over a specific column (e.g. "Save Prof?" over the
 * checkbox column).
 *
 * Both authoring forms (`items` + `row`, or explicit `grid_row`s) are flattened
 * to `rows` by the renderer before they reach here — Grid never sees the
 * distinction.
 */
export function Grid({
	name,
	gridTemplateColumns,
	rowClass,
	className,
	style,
	header,
	rows,
	renderCell,
	renderHeaderCell,
}: GridProps) {
	// `gridTemplateColumns` is already validated + joined by the renderer
	// (`validateColumns`). Applied after the author's `styles` (via `style`) so a
	// schema-set `styles` can't clobber the structural track list, and as inline
	// style so it wins over any helper class on the grid.
	const gridStyle: CSSProperties | undefined = gridTemplateColumns
		? { ...style, gridTemplateColumns }
		: style;

	return (
		<div className={clsx("char-sheet-grid", className)} style={gridStyle}>
			{header != null && header.cells.length > 0 && (
				<div className="char-sheet-grid-header">
					{header.cells.map((cell, i) => (
						<div
							key={cell.id ?? `h${i}`}
							className="char-sheet-grid-header-cell"
							style={
								typeof cell.col === "number" ? { gridColumn: cell.col } : undefined
							}
						>
							{renderHeaderCell(cell, i)}
						</div>
					))}
				</div>
			)}
			{rows.map((row) => (
				<KeyedScopeProvider key={row.key} name={name} itemKey={row.key}>
					<CollapsibleScopeProvider>
						<div className={clsx("char-sheet-grid-row", rowClass, row.rowClass)}>
							{row.cells.map((cell, ci) => renderCell(cell, row.key, ci))}
						</div>
					</CollapsibleScopeProvider>
				</KeyedScopeProvider>
			))}
		</div>
	);
}
