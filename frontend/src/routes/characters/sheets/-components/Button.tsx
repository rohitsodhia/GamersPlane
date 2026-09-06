import clsx from "clsx";
import type { CSSProperties } from "react";
import { type Expr, evaluate, FormulaError, type RefResolver } from "./formula";
import { useRefResolver } from "./loop-context";
import {
	isRepeaterRowAction,
	shouldRenderRowAction,
	useRepeaterRowActions,
} from "./repeater-context";
import { useScopePrefix, useSheetMode, useSheetStore } from "./sheet-values";
import type { ClickAction, RepeaterRowAction, SetValueAction } from "./types";

/**
 * Evaluates a click action's `to` formula to the scalar it will write. A
 * malformed formula yields `undefined` — the click becomes a no-op — DEV-warned,
 * matching how `computed` / `loop` swallow a `FormulaError` rather than throwing
 * out of render or an event handler. Resolver-injected like `evaluate` so it can
 * be unit-tested without the store or React.
 */
export function resolveClickValue(
	to: Expr,
	resolve: RefResolver,
	context: string,
): number | boolean | undefined {
	try {
		return evaluate(to, resolve);
	} catch (err) {
		if (import.meta.env.DEV && err instanceof FormulaError) {
			console.warn(`[sheet] ${context}: on_click.to: ${err.message}`);
		}
		return undefined;
	}
}

interface ButtonProps {
	label: string;
	on_click: ClickAction;
	className?: string;
	style?: CSSProperties;
}

/**
 * A declarative button. Its `on_click` is one of two shapes:
 *  - `{ set, to }` — write a sibling scalar in the current value scope, computed
 *    from `to` at click time (reads `$index`, the target's own value, siblings).
 *    The basis of clocks / tracks.
 *  - `{ row: "add" | "remove" }` — add / remove a row of the enclosing
 *    `repeater`; resolved by position, gated by the repeater's `min` / `max`.
 *
 * The action is declarative data, never code — same threat model as the "no
 * author-supplied CSS / no eval" decisions. In display mode the button renders
 * but does nothing.
 */
export function Button({ label, on_click, className, style }: ButtonProps) {
	// `on_click`'s shape is fixed per schema node, so this branch is stable across
	// renders — each sub-component keeps its own consistent hook order.
	return isRepeaterRowAction(on_click) ? (
		<RowActionButton
			label={label}
			action={on_click}
			className={className}
			style={style}
		/>
	) : (
		<SetValueButton
			label={label}
			action={on_click}
			className={className}
			style={style}
		/>
	);
}

interface VariantProps<A> {
	label: string;
	action: A;
	className?: string;
	style?: CSSProperties;
}

function SetValueButton({
	label,
	action,
	className,
	style,
}: VariantProps<SetValueAction>) {
	const store = useSheetStore();
	const prefix = useScopePrefix();
	const mode = useSheetMode();
	const resolve = useRefResolver();

	const handleClick = () => {
		if (mode !== "edit") return;
		const next = resolveClickValue(action.to, resolve, `button "${label}"`);
		if (next === undefined) return;
		store.set([...prefix, action.set], next);
	};

	return (
		<button
			type="button"
			className={clsx("char-sheet-button", className)}
			style={style}
			onClick={handleClick}
		>
			{label}
		</button>
	);
}

function RowActionButton({
	label,
	action,
	className,
	style,
}: VariantProps<RepeaterRowAction>) {
	const mode = useSheetMode();
	const actions = useRepeaterRowActions();

	if (actions == null) {
		if (import.meta.env.DEV) {
			console.warn(
				`[sheet] button "${label}": on_click.row is only valid inside a repeater's row template`,
			);
		}
		return null;
	}
	if (!shouldRenderRowAction(action.row, actions)) return null;

	const isRemove = action.row === "remove";
	const handleClick = () => {
		if (mode !== "edit") return;
		if (isRemove) actions.removeRow();
		else actions.addRow();
	};

	return (
		<button
			type="button"
			className={clsx(
				"char-sheet-button",
				isRemove ? "char-sheet-repeater-remove" : "char-sheet-repeater-add",
				className,
			)}
			style={style}
			onClick={handleClick}
			aria-label={isRemove ? "Remove row" : undefined}
		>
			{label}
		</button>
	);
}
