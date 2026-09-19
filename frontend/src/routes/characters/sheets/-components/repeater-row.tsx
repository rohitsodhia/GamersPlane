import clsx from "clsx";
import type { ReactNode } from "react";
import { CollapsibleScopeProvider } from "./collapsible-scope";
import { RepeaterRowActionsProvider } from "./repeater-context";
import { CellHeaderIdProvider, ScopeProvider } from "./sheet-values";
import type { AddButtonPos, RowLayout, SheetElement } from "./types";

export interface RepeaterRowParams {
	name: string;
	template: SheetElement[];
	rowKey: string;
	rowIndex: number;
	isLast: boolean;
	rowLayout: RowLayout;
	isGrid: boolean;
	rowClass?: string;
	addButtonPos: AddButtonPos;
	/** The auto-rendered add control for a trailing "row-end" slot, or null (at `max`, or template places its own). */
	addButton: ReactNode;
	canAdd: boolean;
	addRow: () => void;
	canRemove: boolean;
	removeRow: (rowKey: string, rowIndex: number) => void;
	/** From `useHeaderCellIds`: which header id (if any) each headerable cell picks up. */
	headerIds: string[];
	isHeaderable: (type: string) => boolean;
	/** Renders one non-marker template node for this row. See `Repeater`'s `renderCell`. */
	renderCell: (cell: SheetElement, rowKey: string, cellIndex: number) => ReactNode;
}

/**
 * Builds one repeater row: walks `template` in order, wiring headerable cells to
 * their header's `aria-labelledby` id, then wraps the result in the row's value
 * scope and its add/remove-action context (a `button` with
 * `on_click: { row: … }` anywhere in the subtree reads its callbacks from
 * there). Pulled out of `Repeater` so this per-row cell logic — the part most
 * likely to grow new branches as the schema gains node types — can be read and
 * (eventually) tested independently of the add/remove/layout state that owns it.
 */
export function buildRepeaterRow({
	name,
	template,
	rowKey,
	rowIndex,
	isLast,
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
}: RepeaterRowParams): ReactNode {
	const cells: ReactNode[] = [];
	// Advances only on headerable cells, so toggles/collapsibles/action buttons
	// in between don't shift the column alignment with `headerIds`.
	let fieldPos = 0;

	template.forEach((node, i) => {
		if (isHeaderable(node.type)) {
			const headerId = headerIds[fieldPos++];
			cells.push(
				<CellHeaderIdProvider key={node.id ?? `cell-${i}`} headerId={headerId}>
					{renderCell(node, rowKey, i)}
				</CellHeaderIdProvider>,
			);
			return;
		}
		cells.push(renderCell(node, rowKey, i));
	});

	// "row-end" with no template-placed add button: the add control trails the cells.
	if (isLast && addButtonPos === "row-end" && addButton) {
		cells.push(
			<span key="add-end" className="char-sheet-repeater-add-cell">
				{addButton}
			</span>,
		);
	}

	return (
		<ScopeProvider key={rowKey} name={name} index={rowIndex}>
			<CollapsibleScopeProvider>
				<RepeaterRowActionsProvider
					value={{
						addRow,
						removeRow: () => removeRow(rowKey, rowIndex),
						canAdd,
						canRemove,
						isLastRow: isLast,
					}}
				>
					<div
						className={clsx(
							"char-sheet-repeater-row",
							`char-sheet-repeater-row--${rowLayout}`,
							isGrid && "char-sheet-repeater-row--grid",
							rowClass,
						)}
					>
						{cells}
					</div>
				</RepeaterRowActionsProvider>
			</CollapsibleScopeProvider>
		</ScopeProvider>
	);
}
