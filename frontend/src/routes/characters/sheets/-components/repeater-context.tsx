// Render-context plumbing for a `repeater`'s add / remove controls.
//
// The controls are owned by the `Repeater` component, never authorable elements.
// A `button` with an `on_click` of `{ row: "add" }` / `{ row: "remove" }` only
// *marks the spot* in the row template: it binds to the enclosing repeater by
// position (no `name` reference — the rejected `ref`/`for` design), reading the
// actual add / remove callbacks and the `min`/`max` gating state from this
// context, which `Repeater` publishes once per row.

import { createContext, type ReactNode, useContext } from "react";
import type { ClickAction, RepeaterRowAction, SheetElement } from "./types";

export interface RepeaterRowActions {
	/** Append a row (no-op at `max`). */
	addRow: () => void;
	/** Remove the row this context wraps (no-op at `min`). */
	removeRow: () => void;
	/** False at `max` — an "add" button hides. */
	canAdd: boolean;
	/** False at `min` — a "remove" button hides. */
	canRemove: boolean;
	/** True only for the last row — where the single "add" button renders. */
	isLastRow: boolean;
}

const RepeaterRowActionsContext = createContext<RepeaterRowActions | null>(null);

/** Wraps one repeater row so a `row`-action `button` inside it finds its controls. */
export function RepeaterRowActionsProvider({
	value,
	children,
}: {
	value: RepeaterRowActions;
	children: ReactNode;
}) {
	return (
		<RepeaterRowActionsContext.Provider value={value}>
			{children}
		</RepeaterRowActionsContext.Provider>
	);
}

/** The enclosing repeater row's add / remove controls, or null outside a repeater. */
export function useRepeaterRowActions(): RepeaterRowActions | null {
	return useContext(RepeaterRowActionsContext);
}

/** Narrows a `button`'s `on_click` to the add / remove-row variant. */
export function isRepeaterRowAction(action: ClickAction): action is RepeaterRowAction {
	return "row" in action;
}

/**
 * Whether a `row`-action button should render this row, given the row's context.
 * Mirrors the old marker rules: the single "add" button shows on the last row
 * only and hides at `max`; a "remove" button shows on every row and hides at
 * `min`.
 */
export function shouldRenderRowAction(
	row: "add" | "remove",
	actions: RepeaterRowActions,
): boolean {
	return row === "add" ? actions.isLastRow && actions.canAdd : actions.canRemove;
}

/**
 * True when `nodes` (a repeater's row template, walked recursively) places its
 * own add button — in which case `Repeater` suppresses the auto-rendered one and
 * its `add_button_pos`. Only "add" matters here: there is no auto-rendered
 * remove control to suppress.
 */
export function templatePlacesAddButton(nodes: SheetElement[]): boolean {
	return nodes.some((node) => {
		if (
			node.type === "button" &&
			isRepeaterRowAction(node.on_click) &&
			node.on_click.row === "add"
		) {
			return true;
		}
		const children = (node as { content?: SheetElement[] }).content;
		return Array.isArray(children) && templatePlacesAddButton(children);
	});
}
