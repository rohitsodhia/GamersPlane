// Open/closed state for `collapsible` regions and their external
// `collapsible-toggle`s.
//
// A collapsible's trigger can't live inside the region it hides — it would be
// hidden with it — so the two are wired by `name` through a scope here rather
// than by nesting. A scope is minted at the sheet root and once per repeater /
// grid row, so a toggle with `target: "notes"` and the `collapsible` it drives
// resolve against the SAME state even when several rows each carry a "notes"
// pair (independent per row).

import {
	createContext,
	type ReactNode,
	useContext,
	useId,
	useLayoutEffect,
	useMemo,
	useState,
} from "react";

interface CollapsibleScope {
	/** Current open state for `name`; `fallback` while nothing is registered. */
	isOpen(name: string, fallback: boolean): boolean;
	/** Flip `name` (treated as closed if it was never registered). */
	toggle(name: string): void;
	/** Record a region's initial state — first call per `name` wins. */
	register(name: string, open: boolean): void;
	/** Stable DOM id for `name`'s region body, derived the same on both ends. */
	bodyId(name: string): string;
}

const CollapsibleScopeContext = createContext<CollapsibleScope | null>(null);

/**
 * Provides one collapsible scope to its subtree. Rendered at the sheet root and
 * wrapped around every repeater / grid row.
 */
export function CollapsibleScopeProvider({ children }: { children: ReactNode }) {
	const scopeId = useId();
	const [open, setOpen] = useState<Record<string, boolean>>({});

	// `open` is in the dep list so the context value changes identity on every
	// toggle/register — that is what wakes the consuming `Collapsible`s and
	// toggles (a memoised-stable value would leave them frozen).
	const value = useMemo<CollapsibleScope>(
		() => ({
			isOpen: (name, fallback) => (Object.hasOwn(open, name) ? open[name] : fallback),
			toggle: (name) => setOpen((o) => ({ ...o, [name]: !(o[name] ?? false) })),
			register: (name, initial) =>
				setOpen((o) => (Object.hasOwn(o, name) ? o : { ...o, [name]: initial })),
			bodyId: (name) => `${scopeId}-collapsible-${name}`,
		}),
		[scopeId, open],
	);

	return (
		<CollapsibleScopeContext.Provider value={value}>
			{children}
		</CollapsibleScopeContext.Provider>
	);
}

function useCollapsibleScope(): CollapsibleScope {
	const ctx = useContext(CollapsibleScopeContext);
	if (ctx === null) {
		throw new Error("collapsible elements require <CollapsibleScopeProvider>");
	}
	return ctx;
}

/**
 * State for a `collapsible` region: registers its initial open state (from
 * `collapsed`) with the scope, then reports the live open flag and body id. The
 * registration runs in a layout effect, so the very first render falls back to
 * `!collapsed` and the DOM settles before paint.
 */
export function useCollapsible(name: string, collapsed: boolean) {
	const scope = useCollapsibleScope();
	// biome-ignore lint/correctness/useExhaustiveDependencies: `collapsed` is an authoring value, not runtime state; register no-ops after the first call anyway
	useLayoutEffect(() => {
		scope.register(name, !collapsed);
	}, [scope, name]);
	return { open: scope.isOpen(name, !collapsed), bodyId: scope.bodyId(name) };
}

/**
 * State for a `collapsible-toggle`: the target region's open flag, its body id
 * (for `aria-controls`), and the flip handler.
 */
export function useCollapsibleToggle(target: string) {
	const scope = useCollapsibleScope();
	return {
		open: scope.isOpen(target, false),
		bodyId: scope.bodyId(target),
		toggle: () => scope.toggle(target),
	};
}
