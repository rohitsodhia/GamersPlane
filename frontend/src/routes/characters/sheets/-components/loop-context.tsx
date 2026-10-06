// Render-context plumbing for `loop` / `list`, plus the shared ref resolver that
// every formula-evaluation site uses.
//
// A `loop` adds no *value* scope (see `LoopElement` in `types.ts`) — it only
// publishes an iteration index (and, for the `items` form, the current entry) so
// the body's formulas can read `$index` and the entry's fields (`$item.<key>`). `list` publishes
// a flag so a `loop` nested inside it knows to emit `<li>` elements.

import { createContext, type ReactNode, useContext, useMemo } from "react";
import type { RefResolver } from "./formula";
import { resolveRefPath } from "./refs";
import { type Path, type Scope, useScope, useSheetStore } from "./sheet-values";

interface LoopCtx {
	/** 0-based iteration index of the nearest enclosing `loop`. */
	index: number;
	/** The current `items` entry (author data), or null for a `count` loop. */
	item: Record<string, unknown> | null;
}

const LoopContext = createContext<LoopCtx | null>(null);

/**
 * Wraps one `loop` iteration's subtree so its body can resolve `$index` and the
 * current `items` entry's fields. A fresh context object per render is fine here:
 * this wraps a single small iteration, not the whole sheet, and `index` / `item`
 * are stable for a given rendered iteration.
 */
export function LoopIterationProvider({
	index,
	item,
	children,
}: {
	index: number;
	item: Record<string, unknown> | null;
	children: ReactNode;
}) {
	return (
		<LoopContext.Provider value={{ index, item }}>{children}</LoopContext.Provider>
	);
}

/** The nearest enclosing `loop`'s iteration context, or null outside any loop. */
export function useLoopContext(): LoopCtx | null {
	return useContext(LoopContext);
}

// --- list mode --------------------------------------------------------------

const ListModeContext = createContext(false);

/** Marks the subtree as being inside a `list`, so a `loop` emits `<li>`s. */
export function ListModeProvider({ children }: { children: ReactNode }) {
	return <ListModeContext.Provider value={true}>{children}</ListModeContext.Provider>;
}

/** True when rendered inside a `list` (a `loop` should emit `<li>` elements). */
export function useListMode(): boolean {
	return useContext(ListModeContext);
}

// --- ref resolver ---------------------------------------------------------------

const ITEM_PREFIX = "$item.";

/**
 * The resolver every formula-evaluation site shares (`computed` text,
 * `class_when` / `style_when`, a `loop`'s `count`, a `button`'s `on_click.to`):
 *   - `$index` — the nearest `loop`'s 0-based iteration index (0 outside a loop)
 *   - `$item.<key>` — that key of the nearest `loop`'s current `items` entry
 *   - anything else — the value store, at the path `resolveRefPath` gives
 *     (`stats.str.mod` from the root, `$row.x` from the current row), with
 *     any `$(inner)` segment read through this same resolver
 *
 * Anything unresolvable is `undefined` (which `evaluate` coerces to 0).
 */
export function createRefResolver(
	get: (path: Path) => unknown,
	scope: Scope,
	loop: LoopCtx | null,
): RefResolver {
	const resolve = (ref: string): unknown => {
		if (ref === "$index") return loop?.index ?? 0;
		if (ref.startsWith(ITEM_PREFIX)) {
			const key = ref.slice(ITEM_PREFIX.length);
			return loop?.item && Object.hasOwn(loop.item, key) ? loop.item[key] : undefined;
		}
		const path = resolveRefPath(ref, scope, resolve);
		return path ? get(path) : undefined;
	};
	return resolve;
}

/** `createRefResolver` bound to the current store, scope, and loop. */
export function useRefResolver(): RefResolver {
	const store = useSheetStore();
	const scope = useScope();
	const loop = useLoopContext();
	return useMemo(
		() => createRefResolver((path) => store.get(path), scope, loop),
		[store, scope, loop],
	);
}
