import clsx from "clsx";
import {
	type CSSProperties,
	type ReactNode,
	useCallback,
	useRef,
	useSyncExternalStore,
} from "react";
import { type Expr, evaluate, FormulaError } from "./formula";
import { useRefResolver } from "./loop-context";
import { useScopePrefix, useSheetStore } from "./sheet-values";
import { resolveStyles } from "./style-allowlist";
import type { StyleBundle, StyleWhen } from "./types";

/**
 * Pure part of `class_when` / `style_when`: given a ref resolver, returns the
 * currently-active class tokens and the merged conditional style bundle. A
 * formula that throws (`FormulaError`) counts as falsy (DEV-warned), matching
 * `computed`'s leniency. Kept resolver-injected — like `evaluate` — so it can be
 * unit-tested without the store or React.
 */
export function resolveWhen(
	classWhen: Record<string, Expr> | undefined,
	styleWhen: StyleWhen[] | undefined,
	resolve: (ref: string) => unknown,
	context: string,
): { classes: string[]; styleBundle: StyleBundle } {
	const truthy = (expr: Expr): boolean => {
		try {
			return Boolean(evaluate(expr, resolve));
		} catch (err) {
			if (import.meta.env.DEV && err instanceof FormulaError) {
				console.warn(`[sheet] ${context}: when-condition: ${err.message}`);
			}
			return false;
		}
	};

	const classes = classWhen
		? Object.keys(classWhen).filter((token) => truthy(classWhen[token]))
		: [];
	const styleBundle: StyleBundle = styleWhen
		? Object.assign(
				{},
				...styleWhen.filter((entry) => truthy(entry.when)).map((entry) => entry.styles),
			)
		: {};

	return { classes, styleBundle };
}

interface WhenStyledProps {
	classWhen?: Record<string, Expr>;
	styleWhen?: StyleWhen[];
	/** Static `className` / `style` already resolved by `commonDomProps`. */
	base: { className?: string; style?: CSSProperties };
	/** Path string, for DEV warnings only. */
	context: string;
	/** Rendered with the merged `className` / `style` to spread onto the element. */
	children: (merged: { className?: string; style?: CSSProperties }) => ReactNode;
}

/**
 * Wraps one element so its `class_when` / `style_when` conditions are evaluated
 * against the current value scope and re-applied whenever a referenced value
 * changes. Subscribes to the whole scope prefix (like `computed`) so any sibling
 * write re-runs the conditions. Returns a stable merged object while the active
 * set is unchanged, so it is safe as a `useSyncExternalStore` snapshot.
 */
export function WhenStyled({
	classWhen,
	styleWhen,
	base,
	context,
	children,
}: WhenStyledProps) {
	const store = useSheetStore();
	const prefix = useScopePrefix();
	const resolve = useRefResolver();

	const subscribe = useCallback(
		(cb: () => void) => store.subscribe(prefix, cb),
		[store, prefix],
	);

	const cache = useRef<{
		key: string;
		merged: { className?: string; style?: CSSProperties };
	} | null>(null);

	const getSnapshot = useCallback(() => {
		const { classes, styleBundle } = resolveWhen(
			classWhen,
			styleWhen,
			resolve,
			context,
		);
		const condStyle = resolveStyles(styleBundle, context);
		const key = JSON.stringify([
			classes,
			condStyle ?? null,
			base.className ?? null,
			base.style ?? null,
		]);
		if (cache.current?.key !== key) {
			cache.current = {
				key,
				merged: {
					className: clsx(base.className, classes) || undefined,
					style: base.style || condStyle ? { ...base.style, ...condStyle } : undefined,
				},
			};
		}
		return cache.current.merged;
	}, [resolve, classWhen, styleWhen, base.className, base.style, context]);

	const merged = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
	return <>{children(merged)}</>;
}
