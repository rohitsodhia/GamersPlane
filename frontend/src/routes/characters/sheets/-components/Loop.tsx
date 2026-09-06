import clsx from "clsx";
import {
	type CSSProperties,
	type ReactNode,
	useCallback,
	useMemo,
	useSyncExternalStore,
} from "react";
import { type Expr, evaluate, FormulaError, type RefResolver } from "./formula";
import { LoopIterationProvider, useListMode, useRefResolver } from "./loop-context";
import { useScopePrefix, useSheetStore } from "./sheet-values";
import type { SheetElement, StyleWhen } from "./types";
import { WhenStyled } from "./when-styling";

/** Hard ceiling on a `loop`'s iteration count, so a runaway formula can't hang. */
export const MAX_LOOP_ITERATIONS = 200;

/**
 * A `loop`'s `count` → an integer iteration count: a literal passes through, a
 * formula is evaluated against `resolve`. Floored, and clamped to
 * `[0, MAX_LOOP_ITERATIONS]`; a non-finite / negative result or a malformed
 * formula yields 0 (DEV-warned).
 */
export function resolveLoopCount(
	count: number | Expr,
	resolve: RefResolver,
	context: string,
): number {
	let raw: number;
	if (typeof count === "number") {
		raw = count;
	} else {
		try {
			raw = Number(evaluate(count, resolve));
		} catch (err) {
			if (import.meta.env.DEV && err instanceof FormulaError) {
				console.warn(`[sheet] ${context}: loop count: ${err.message}`);
			}
			return 0;
		}
	}
	if (!Number.isFinite(raw) || raw <= 0) return 0;
	return Math.min(Math.floor(raw), MAX_LOOP_ITERATIONS);
}

export interface LoopIteration {
	index: number;
	/** The `items` entry for this iteration, or null for a `count` loop. */
	item: Record<string, unknown> | null;
}

/**
 * Flattens a `loop`'s two authoring forms into the iteration list the component
 * renders. `items` wins if both are set (DEV-warned); neither set renders
 * nothing (DEV-warned). Both forms are capped at `MAX_LOOP_ITERATIONS`.
 */
export function computeLoopIterations(
	spec: {
		items?: readonly Record<string, unknown>[];
		count?: number | Expr;
	},
	resolve: RefResolver,
	context: string,
): LoopIteration[] {
	if (spec.items != null) {
		if (spec.count != null && import.meta.env.DEV) {
			console.warn(
				`[sheet] ${context}: loop has both "items" and "count"; ignoring "count"`,
			);
		}
		return spec.items
			.slice(0, MAX_LOOP_ITERATIONS)
			.map((item, index) => ({ index, item }));
	}
	if (spec.count == null) {
		if (import.meta.env.DEV) {
			console.warn(
				`[sheet] ${context}: loop has neither "items" nor "count"; nothing to render`,
			);
		}
		return [];
	}
	const n = resolveLoopCount(spec.count, resolve, context);
	return Array.from({ length: n }, (_, index) => ({ index, item: null }));
}

interface LoopProps {
	items?: Record<string, string | number | boolean | null>[];
	count?: number | Expr;
	/** The template, rendered once per iteration. */
	template: SheetElement[];
	/** Static class for each iteration's element (from the node's `class`). */
	itemClassName?: string;
	/** Static style for each iteration's element (from the node's `styles`). */
	itemStyle?: CSSProperties;
	/** Per-iteration conditional class (the node's `class_when`), evaluated with `$index` in scope. */
	classWhen?: Record<string, Expr>;
	/** Per-iteration conditional style (the node's `style_when`). */
	styleWhen?: StyleWhen[];
	/** Node path, for DEV warnings. */
	context: string;
	/** Renders one template node for the given iteration. Owned by the renderer. */
	renderBody: (cell: SheetElement, index: number, cellIndex: number) => ReactNode;
}

/**
 * Repeats `template` once per iteration (see `LoopElement`). Adds no value scope
 * — it only wraps each iteration in a `LoopIterationProvider` so the body can
 * read `$index` (and, for the `items` form, the entry's fields). Inside a `list`
 * each iteration is an `<li>`; otherwise a block `char-sheet-loop-item` element.
 * The node's `class` / `styles` / `class_when` / `style_when` apply per
 * iteration (so a condition can key off `$index`), not to any outer container —
 * there is none; wrap the `loop` in a `section` / `group` for layout.
 */
export function Loop({
	items,
	count,
	template,
	itemClassName,
	itemStyle,
	classWhen,
	styleWhen,
	context,
	renderBody,
}: LoopProps) {
	const store = useSheetStore();
	const prefix = useScopePrefix();
	const resolve = useRefResolver();
	const inList = useListMode();

	// Only a formula `count` is dynamic; `items` and a literal `count` are fixed
	// by the schema. Subscribe to the whole scope so a formula recomputes when a
	// referenced field changes; the snapshot is a number, so it stays stable.
	const isDynamicCount = items == null && count != null && typeof count !== "number";
	const subscribe = useCallback(
		(cb: () => void) => store.subscribe(prefix, cb),
		[store, prefix],
	);
	const readDynamicCount = useCallback(
		() => (isDynamicCount ? resolveLoopCount(count as Expr, resolve, context) : 0),
		[isDynamicCount, count, resolve, context],
	);
	const dynamicCount = useSyncExternalStore(
		subscribe,
		readDynamicCount,
		readDynamicCount,
	);

	const iterations = useMemo(
		() =>
			computeLoopIterations(
				{ items, count: isDynamicCount ? dynamicCount : (count as number | undefined) },
				resolve,
				context,
			),
		[items, count, isDynamicCount, dynamicCount, resolve, context],
	);

	const ItemTag = inList ? "li" : "div";
	const baseClassName =
		clsx(!inList && "char-sheet-loop-item", itemClassName) || undefined;
	const hasWhen = classWhen != null || styleWhen != null;

	return (
		<>
			{iterations.map(({ index, item }) => (
				<LoopIterationProvider key={index} index={index} item={item}>
					{hasWhen ? (
						<WhenStyled
							classWhen={classWhen}
							styleWhen={styleWhen}
							base={{ className: baseClassName, style: itemStyle }}
							context={`${context}[${index}]`}
						>
							{(merged) => (
								<ItemTag {...merged}>
									{template.map((cell, ci) => renderBody(cell, index, ci))}
								</ItemTag>
							)}
						</WhenStyled>
					) : (
						<ItemTag className={baseClassName} style={itemStyle}>
							{template.map((cell, ci) => renderBody(cell, index, ci))}
						</ItemTag>
					)}
				</LoopIterationProvider>
			))}
		</>
	);
}
