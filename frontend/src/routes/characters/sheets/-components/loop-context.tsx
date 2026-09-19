// Render-context plumbing for `loop` / `list`, plus the shared ref resolver that
// every formula-evaluation site uses.
//
// A `loop` adds no *value* scope (see `LoopElement` in `types.ts`) — it only
// publishes an iteration index (and, for the `items` form, the current entry) so
// the body's formulas can read `$index` and the entry's fields. `list` publishes
// a flag so a `loop` nested inside it knows to emit `<li>` elements.

import { createContext, type ReactNode, useContext, useMemo } from "react";
import type { RefResolver } from "./formula";
import { type Path, useScopePrefix, useSheetStore } from "./sheet-values";

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

/**
 * The resolver every formula-evaluation site shares (`computed` text,
 * `class_when` / `style_when`, a `loop`'s `count`). Resolution order:
 *   1. `$index` — the nearest `loop`'s 0-based iteration index (0 outside a loop)
 *   2. a key of the current `loop` `items` entry
 *   3. the value store, at `[...scopePrefix, ref]`
 *
 * A `$`-prefixed name never falls through to the store: an unknown `$foo`
 * resolves to `undefined` (which `evaluate` then coerces to 0).
 */
export function createRefResolver(
	get: (path: Path) => unknown,
	prefix: Path,
	loop: LoopCtx | null,
): RefResolver {
	return (ref: string) => {
		if (ref === "$index") return loop?.index ?? 0;
		if (ref.startsWith("$")) return undefined;
		if (loop?.item && Object.hasOwn(loop.item, ref)) return loop.item[ref];
		return get([...prefix, ref]);
	};
}

/** `createRefResolver` bound to the current store, scope prefix, and loop. */
export function useRefResolver(): RefResolver {
	const store = useSheetStore();
	const prefix = useScopePrefix();
	const loop = useLoopContext();
	return useMemo(
		() => createRefResolver((path) => store.get(path), prefix, loop),
		[store, prefix, loop],
	);
}
