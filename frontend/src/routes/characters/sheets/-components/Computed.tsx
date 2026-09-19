import clsx from "clsx";
import {
	type CSSProperties,
	useCallback,
	useEffect,
	useId,
	useSyncExternalStore,
} from "react";
import { type Expr, evaluate, FormulaError, type FormulaValue } from "./formula";
import { useRefResolver } from "./loop-context";
import {
	useScopedPath,
	useScopePrefix,
	useSheetMode,
	useSheetStore,
} from "./sheet-values";
import type { ComputedFormat } from "./types";

interface ComputedProps {
	name: string;
	formula: Expr;
	format?: ComputedFormat;
	className?: string;
	style?: CSSProperties;
}

/**
 * The computed branch of the `text` element (dispatched from `Text.tsx`): a
 * read-only value derived from other fields. `formula` (an AST — see
 * `formula.ts`) is evaluated against the current value scope, so `{ ref: "score" }`
 * inside a `grid` row for `str` reads `stats.str.score`. It recomputes whenever
 * anything in that scope changes.
 *
 * In edit mode the result is also written back to the store under `name`, so
 * other elements' formulas (and the saved character) can read it. Display mode
 * only reads — the store is authoritative there and must not be mutated.
 *
 * Ref resolution is scope-local for now: lexical outward / sheet-scope (`$.`)
 * refs, indirect `value(...)` refs and the cross-field dependency graph are the
 * reactivity engine's job, still deferred.
 */
export function Computed({ name, formula, format, className, style }: ComputedProps) {
	const domId = useId();
	const mode = useSheetMode();
	const store = useSheetStore();
	const prefix = useScopePrefix();
	const selfPath = useScopedPath(name);
	const resolve = useRefResolver();

	// notify() wakes every ancestor of a changed path, so subscribing at the
	// scope prefix catches every sibling field the formula might reference.
	const subscribe = useCallback(
		(cb: () => void) => store.subscribe(prefix, cb),
		[store, prefix],
	);

	const getSnapshot = useCallback((): FormulaValue => {
		try {
			return evaluate(formula, resolve);
		} catch (err) {
			if (import.meta.env.DEV && err instanceof FormulaError) {
				console.warn(`[sheet] computed "${name}": ${err.message}`);
			}
			return 0;
		}
	}, [resolve, formula, name]);

	// Primitive result — useSyncExternalStore's Object.is check makes it stable
	// across renders when nothing changed, so no extra memo is needed.
	const value = useSyncExternalStore(subscribe, getSnapshot);

	useEffect(() => {
		if (mode !== "edit") return;
		if (store.get(selfPath) !== value) store.set(selfPath, value);
	}, [mode, store, selfPath, value]);

	return (
		<div
			className={clsx("char-sheet-field", "char-sheet-field--text", className)}
			style={style}
		>
			<span id={domId} className="char-sheet-value char-sheet-text-value">
				{formatValue(value, format)}
			</span>
		</div>
	);
}

function formatValue(value: FormulaValue, format: ComputedFormat = "number"): string {
	if (typeof value === "boolean") return value ? "yes" : "no";
	if (Number.isNaN(value)) return "";
	if (format === "signed") return value >= 0 ? `+${value}` : String(value);
	return String(value);
}
