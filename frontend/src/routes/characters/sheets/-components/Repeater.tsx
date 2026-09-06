import clsx from "clsx";
import { type CSSProperties, type ReactNode, useEffect, useRef, useState } from "react";
import { templatePlacesAddButton } from "./repeater-context";
import { buildRepeaterRow } from "./repeater-row";
import { useHeaderCellIds, useRepeaterRows } from "./sheet-values";
import type { AddButtonPos, RowLayout, SheetElement } from "./types";

interface RepeaterProps {
	name: string;
	/** The row template, straight from the schema node's `content`. */
	template: SheetElement[];
	/** Column headers, straight from the schema node's `header`. Rendered once. */
	header?: SheetElement[];
	rowLayout?: RowLayout;
	/**
	 * Pre-validated `grid-template-columns` value (see `validateColumns`). When
	 * set, the repeater switches to grid mode: `header` and every row lay out as
	 * CSS-grid subgrids of these tracks (see `Grid`) so header text sits over its
	 * column's inputs instead of just flexing next to it.
	 */
	gridTemplateColumns?: string;
	rowClass?: string;
	addLabel?: string;
	addClass?: string;
	addButtonPos?: AddButtonPos;
	min?: number;
	max?: number;
	className?: string;
	style?: CSSProperties;
	/**
	 * Renders one non-marker template node for a given row. The renderer owns
	 * this so recursion, keying, and unknown-type handling stay in one place;
	 * the Repeater only decides how many rows exist and where its own controls go.
	 */
	renderCell: (cell: SheetElement, rowKey: string, cellIndex: number) => ReactNode;
	/** Renders one header cell. Same rationale as `renderCell`. */
	renderHeaderCell: (cell: SheetElement, index: number) => ReactNode;
}

/**
 * A repeatable group of fields. `template` is rendered once per row; the add /
 * remove controls are owned here (not authorable elements), positioned either by
 * `add_button_pos` or by a `button` with `on_click: { row: "add" | "remove" }`
 * dropped into the template (bound to this repeater by position, gated here by
 * `min` / `max`). Row identity is a stable generated key, never the index, so
 * removing a middle row doesn't remount its siblings.
 *
 * Each row's fields bind to `values[name][rowIndex][<field name>]` via the
 * <ScopeProvider> wrapper; add/remove keep that stored array index-aligned with
 * the key list.
 */
export function Repeater({
	name,
	template,
	header,
	rowLayout = "stack",
	gridTemplateColumns,
	rowClass,
	addLabel = "Add",
	addClass,
	addButtonPos = "bottom",
	min = 0,
	max,
	className,
	style,
	renderCell,
	renderHeaderCell,
}: RepeaterProps) {
	const { rows: storedRows, append, removeAt, ensureCount } = useRepeaterRows(name);

	// One DOM id per header cell, handed to each row's headerable cells in
	// order — see `useCellAriaLabelledBy`.
	const { headerIds, isHeaderable } = useHeaderCellIds(header);

	// A validated `gridTemplateColumns` switches on grid mode: the tracks are set
	// on the repeater container and header + each row become subgrids of them
	// (mirrors `Grid`) so cells line up under their header instead of flexing
	// independently. Applied after the author's `styles` (via `style`) so it
	// can't clobber the structural track list.
	const isGrid = gridTemplateColumns != null;
	const gridStyle: CSSProperties | undefined = isGrid
		? { ...style, gridTemplateColumns }
		: style;

	const nextId = useRef(0);
	const makeId = () => `r${nextId.current++}`;
	// One stable key per visible row, for React identity across add/remove. Seeded
	// from however many rows the character already has, clamped up to `min` and to
	// at least one so the fields are visible.
	const [keys, setKeys] = useState<string[]>(() =>
		Array.from({ length: Math.max(storedRows.length, min, 1) }, makeId),
	);

	// Give the stored array a slot for every visible row, so an untouched repeater
	// round-trips as `[{}, ...]` instead of a sparse array. Mount-only.
	// biome-ignore lint/correctness/useExhaustiveDependencies: one-time seed
	useEffect(() => {
		ensureCount(keys.length);
	}, []);

	const canAdd = max == null || keys.length < max;
	const canRemove = keys.length > min;

	const addRow = () => {
		if (!canAdd) return;
		setKeys((k) => [...k, makeId()]);
		append();
	};
	const removeRow = (rowKey: string, rowIndex: number) => {
		if (!canRemove) return;
		setKeys((k) => k.filter((key) => key !== rowKey));
		removeAt(rowIndex);
	};

	// The template may place its own add button (`on_click: { row: "add" }`); then
	// the auto-rendered control and its `add_button_pos` stand down entirely.
	const templateAdd = templatePlacesAddButton(template);
	// An explicit add button or "row-end" both sit inline with the last row, so
	// the standalone header/top/bottom placements must stand down.
	const inlineAdd = templateAdd || addButtonPos === "row-end";

	const addButton =
		!templateAdd && canAdd ? (
			<button
				type="button"
				className={clsx("char-sheet-repeater-add", addClass)}
				onClick={addRow}
			>
				{addLabel}
			</button>
		) : null;

	const renderRow = (rowKey: string, rowIndex: number) =>
		buildRepeaterRow({
			name,
			template,
			rowKey,
			rowIndex,
			isLast: rowIndex === keys.length - 1,
			rowLayout,
			isGrid,
			rowClass,
			addButtonPos,
			addButton,
			canAdd,
			addRow,
			canRemove,
			removeRow,
			headerIds,
			isHeaderable,
			renderCell,
		});

	const showHeader = (header != null && header.length > 0) || addButtonPos === "header";

	return (
		<div
			className={clsx(
				"char-sheet-repeater",
				isGrid && "char-sheet-repeater--grid",
				className,
			)}
			style={gridStyle}
		>
			{showHeader && (
				<div
					className={clsx(
						"char-sheet-repeater-header",
						isGrid && "char-sheet-repeater-header--grid",
					)}
				>
					{header?.map((cell, i) => (
						<div
							key={cell.id ?? `h${i}`}
							id={headerIds[i]}
							className="char-sheet-repeater-header-cell"
							style={
								typeof cell.col === "number" ? { gridColumn: cell.col } : undefined
							}
						>
							{renderHeaderCell(cell, i)}
						</div>
					))}
					{addButtonPos === "header" && !inlineAdd && addButton}
				</div>
			)}
			{addButtonPos === "top" && !inlineAdd && (
				<div className="char-sheet-repeater-add-wrap">{addButton}</div>
			)}
			<div
				className={clsx(
					"char-sheet-repeater-rows",
					// `display: contents` in grid mode: the wrapper drops out of the box
					// tree so each row is a direct grid item of `.char-sheet-repeater--grid`
					// (a subgrid row needs a real grid ancestor immediately above it).
					isGrid && "char-sheet-repeater-rows--grid",
				)}
			>
				{keys.map((rowKey, i) => renderRow(rowKey, i))}
			</div>
			{addButtonPos === "bottom" && !inlineAdd && (
				<div className="char-sheet-repeater-add-wrap">{addButton}</div>
			)}
		</div>
	);
}
