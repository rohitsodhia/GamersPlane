// Controlled value store for a rendered character sheet.
//
// The sheet schema is a tree, but the *values* a user types mirror the sheet's
// SCOPE structure, not its visual structure:
//   - a scalar control (`input`, `select`, `textarea`, `checkbox`, ...)
//     contributes one key to its current scope: `name -> value`
//   - a `section` is transparent: its children write into the parent scope
//   - a `repeater` contributes one key holding an ARRAY of child-scope objects,
//     one per row: `name -> [{ ...row }, { ...row }]`
//   - a `grid` contributes one key holding an OBJECT of child-scope objects,
//     one per author-fixed row: `name -> { str: { ...row }, dex: {…} }`
//
// So the value document for the test sheet looks like:
//   { name: "Gandalf", class: "Wizard",
//     classes: [{ class: "Wizard", level: "20" }, { class: "Fighter", level: "2" }],
//     stats: { str: { score: "15", mod: 2 }, dex: { score: "10", mod: 0 } } }
//
// Nesting only ever happens at a repeater or grid boundary. A field addresses
// its value by a PATH: the accumulated scope prefix (from context) plus its own
// `name`, e.g. ["classes", 0, "level"] or ["stats", "str", "mod"]. Repeater rows
// push `name` + row index via <ScopeProvider>; grid rows push `name` + row key
// via <KeyedScopeProvider>.
//
// The store is a thin external store (useSyncExternalStore) so a keystroke
// re-renders only the field that changed, and so the future reactivity engine
// can subscribe to the same slices and write computed values back. The same
// store backs display mode: it is seeded from the character's stored values and
// simply never written to.

import {
	createContext,
	type ReactNode,
	useCallback,
	useContext,
	useId,
	useLayoutEffect,
	useMemo,
	useRef,
	useSyncExternalStore,
} from "react";

export type Scalar = string | number | boolean | null;
/** A single scope object. Array values belong to repeater keys only. */
export type ScopeValues = { [name: string]: Scalar | ScopeValues[] | undefined };
export type Path = (string | number)[];

export type SheetMode = "edit" | "display";

export interface SheetStore {
	/** Read the value at `path`; `undefined` when nothing is stored there. */
	get(path: Path): unknown;
	/** Write `value` at `path`, creating intermediate containers as needed. */
	set(path: Path, value: unknown): void;
	/** Subscribe to changes at `path` or any descendant of it. */
	subscribe(path: Path, cb: () => void): () => void;
	/** Deep copy of the whole value document, for submitting. */
	snapshot(): ScopeValues;
}

// Unit-separator: safe between path segments, won't collide with field names.
const PATH_SEP = "\x1f";
const keyOf = (path: Path) => path.join(PATH_SEP);

export function createSheetStore(initial: ScopeValues = {}): SheetStore {
	// Deep-clone in so callers can't mutate our tree (and vice versa on snapshot).
	let root: ScopeValues = structuredClone(initial ?? {});
	const listeners = new Map<string, Set<() => void>>();

	function readAt(path: Path): unknown {
		let node: unknown = root;
		for (const seg of path) {
			if (node == null || typeof node !== "object") return undefined;
			node = (node as Record<string | number, unknown>)[seg as never];
		}
		return node;
	}

	function writeAt(path: Path, value: unknown): void {
		if (path.length === 0) {
			root = (value ?? {}) as ScopeValues;
			return;
		}
		let node = root as Record<string | number, unknown>;
		for (let i = 0; i < path.length - 1; i++) {
			const seg = path[i];
			const next = node[seg];
			if (next == null || typeof next !== "object") {
				// The next segment's type decides the container: a number means the
				// child is an array index (repeater rows), anything else an object.
				node[seg] = typeof path[i + 1] === "number" ? [] : {};
			}
			node = node[seg] as Record<string | number, unknown>;
		}
		node[path[path.length - 1]] = value;
	}

	function notify(path: Path): void {
		// Notify the exact path and every ancestor: a repeater subscribes to
		// ["classes"] and must hear about a row splice, while ["classes", 0, "x"]
		// changing should also wake anything watching the row or the array.
		for (let i = path.length; i >= 0; i--) {
			const subs = listeners.get(keyOf(path.slice(0, i)));
			if (subs) for (const cb of subs) cb();
		}
	}

	return {
		get: readAt,
		set(path, value) {
			writeAt(path, value);
			notify(path);
		},
		subscribe(path, cb) {
			const k = keyOf(path);
			let subs = listeners.get(k);
			if (!subs) {
				subs = new Set();
				listeners.set(k, subs);
			}
			subs.add(cb);
			return () => {
				subs.delete(cb);
				if (subs.size === 0) listeners.delete(k);
			};
		},
		snapshot: () => structuredClone(root),
	};
}

interface SheetValuesContext {
	store: SheetStore;
	mode: SheetMode;
}

const ValuesContext = createContext<SheetValuesContext | null>(null);
const EMPTY_PATH: Path = [];
const ScopeContext = createContext<Path>(EMPTY_PATH);

/**
 * Creates the value store (once) and makes it available to every field rendered
 * inside. `SheetRenderer` must be rendered under this provider. Read the store
 * back out with `useSheetStore()` to seed `initialValues` or to `snapshot()` on
 * submit. `mode` is the render mode every element component branches on.
 */
export function SheetValuesProvider({
	initialValues,
	mode = "edit",
	children,
}: {
	initialValues?: ScopeValues;
	mode?: SheetMode;
	children: ReactNode;
}) {
	const storeRef = useRef<SheetStore>(null);
	if (storeRef.current === null) {
		storeRef.current = createSheetStore(initialValues ?? {});
	}
	const value = useMemo<SheetValuesContext>(
		() => ({ store: storeRef.current as SheetStore, mode }),
		[mode],
	);
	return (
		<ValuesContext.Provider value={value}>
			<ScopeContext.Provider value={EMPTY_PATH}>{children}</ScopeContext.Provider>
		</ValuesContext.Provider>
	);
}

function useValuesContext(): SheetValuesContext {
	const ctx = useContext(ValuesContext);
	if (ctx === null) {
		throw new Error("character-sheet value hooks require <SheetValuesProvider>");
	}
	return ctx;
}

export function useSheetStore(): SheetStore {
	return useValuesContext().store;
}

export function useSheetMode(): SheetMode {
	return useValuesContext().mode;
}

/**
 * Pushes `name` + one coordinate segment onto the scope path for a subtree.
 * Explicitly memoised: this becomes a context value for a whole subtree, so a
 * fresh array each render would re-render and re-subscribe every field beneath.
 */
function useChildScope(name: string, segment: string | number): Path {
	const prefix = useContext(ScopeContext);
	return useMemo<Path>(() => [...prefix, name, segment], [prefix, name, segment]);
}

/**
 * Extends the current value scope with `name` + `index` for one repeater row, so
 * the fields inside it read/write ["...prefix", name, index, <field name>]. The
 * numeric segment makes the store create an array container.
 */
export function ScopeProvider({
	name,
	index,
	children,
}: {
	name: string;
	index: number;
	children: ReactNode;
}) {
	const next = useChildScope(name, index);
	return <ScopeContext.Provider value={next}>{children}</ScopeContext.Provider>;
}

/**
 * The `grid` counterpart of `ScopeProvider`: extends the scope with `name` +
 * `itemKey` (a string) for one fixed row, so its fields read/write
 * ["...prefix", name, itemKey, <field name>]. The string segment makes the store
 * create a plain object container (keyed by row, not positional).
 */
export function KeyedScopeProvider({
	name,
	itemKey,
	children,
}: {
	name: string;
	itemKey: string;
	children: ReactNode;
}) {
	const next = useChildScope(name, itemKey);
	return <ScopeContext.Provider value={next}>{children}</ScopeContext.Provider>;
}

// --- Label wiring --------------------------------------------------------------
//
// A `group` mints one DOM id and publishes it here along with the `name` of the
// control that owns it (computed by the renderer: the sole bound control, or the
// one flagged `attach_label`). The owning control renders with that id; every
// `label` in the group points `htmlFor` at it. Controls outside a group, or in a
// group with no determinable owner, fall back to their own `useId()`.

interface FieldDomId {
	id: string;
	/** `name` of the control this id belongs to, or undefined if undeterminable. */
	ownerName?: string;
}

export const FieldDomIdContext = createContext<FieldDomId | null>(null);

/** DOM id a bound control should render with, given its `name`. */
export function useControlDomId(name: string): string {
	const fallback = useId();
	const ctx = useContext(FieldDomIdContext);
	return ctx != null && ctx.ownerName === name ? ctx.id : fallback;
}

/** DOM id a `label` should target, or undefined when it has no group control. */
export function useLabelDomId(): string | undefined {
	return useContext(FieldDomIdContext)?.id;
}

// --- Repeater header wiring -----------------------------------------------
//
// A repeater's `header` is column text describing every row, not a `label` for
// any one row's control (a control can only have one `htmlFor`/labelling
// element). Instead each header cell gets a DOM id, and the row cell it labels
// picks it up as `aria-labelledby`. `Repeater` provides this scoped to exactly
// the subtree of one row cell, so it reaches a bare control or one wrapped in a
// `group` the same way, with no `name` matching needed.

const CellHeaderIdContext = createContext<string | undefined>(undefined);

/** Wraps one row cell's subtree so its control(s) can pick up the header id. */
export function CellHeaderIdProvider({
	headerId,
	children,
}: {
	headerId: string | undefined;
	children: ReactNode;
}) {
	return (
		<CellHeaderIdContext.Provider value={headerId}>
			{children}
		</CellHeaderIdContext.Provider>
	);
}

/** The header cell id a control should render as `aria-labelledby`, if any. */
export function useCellAriaLabelledBy(): string | undefined {
	return useContext(CellHeaderIdContext);
}

/**
 * Template node types that occupy one column of a repeater's `header` (in
 * template order). Everything else — an add/remove `button`,
 * `collapsible-toggle`, `collapsible` (its content has no fixed column, being
 * per-row togglable) — is skipped and consumes no header slot.
 */
const HEADERABLE_TYPES = new Set([
	"group",
	"input",
	"textarea",
	"select",
	"checkbox",
	"text",
]);

/**
 * Mints one stable DOM id per header cell for a repeater (`header` is static
 * per-schema), and exposes which template node types consume one. A row
 * builder walks its own template in order, advancing only on headerable
 * nodes, so markers/toggles/collapsibles in between don't shift the column
 * alignment with these ids.
 */
export function useHeaderCellIds(header: { type: string }[] | undefined): {
	headerIds: string[];
	isHeaderable: (type: string) => boolean;
} {
	const headerBaseId = useId();
	const headerIds = (header ?? []).map((_, i) => `${headerBaseId}-h${i}`);
	return { headerIds, isHeaderable: (type) => HEADERABLE_TYPES.has(type) };
}

/** The absolute value path for `name` in the current scope. */
export function useScopedPath(name: string): Path {
	const prefix = useContext(ScopeContext);
	return useMemo<Path>(() => [...prefix, name], [prefix, name]);
}

/**
 * The accumulated scope prefix (no field name). Stable across renders until a
 * `ScopeProvider` / `KeyedScopeProvider` boundary changes it — used to resolve
 * scope-local refs (e.g. a `class_when` / `style_when` formula) and to subscribe
 * to the whole scope so any sibling change re-evaluates.
 */
export function useScopePrefix(): Path {
	return useContext(ScopeContext);
}

/**
 * Two-way binding for a scalar field. `value` is whatever is stored, falling back
 * to `defaultValue` while nothing is stored; `setValue` writes it back and
 * notifies subscribers. In display mode nothing calls `setValue`, but the read
 * path is identical.
 *
 * When `defaultValue` is given and nothing is stored yet, it is also seeded into
 * the store (edit mode only — the display store is authoritative and never
 * mutated) so an untouched-but-defaulted field still round-trips through
 * `snapshot()`. The seed runs in a layout effect so dependent `computed`s see it
 * before the first paint. An explicit stored `null` or `""` is left alone.
 */
export function useField<T = unknown>(
	name: string,
	defaultValue?: T,
): [T, (value: T) => void] {
	const { store, mode } = useValuesContext();
	const path = useScopedPath(name);
	const subscribe = useCallback(
		(cb: () => void) => store.subscribe(path, cb),
		[store, path],
	);
	const stored = useSyncExternalStore(
		subscribe,
		() => store.get(path) as T | undefined,
	);
	const setValue = useCallback((v: T) => store.set(path, v), [store, path]);

	useLayoutEffect(() => {
		if (mode !== "edit" || defaultValue === undefined) return;
		if (store.get(path) === undefined) store.set(path, defaultValue);
	}, [mode, store, path, defaultValue]);

	const value = (stored === undefined ? defaultValue : stored) as T;
	return [value, setValue];
}

/**
 * The binding every scalar control (`Input`, `Textarea`, `Select`, ...) needs:
 * its DOM id, the current render mode, the header id (if any) it should expose
 * as `aria-labelledby`, and its two-way value binding. Bundling these means a
 * new control can't accidentally wire up only some of them.
 */
export function useControlBinding<T = unknown>(
	name: string,
	defaultValue?: T,
): {
	domId: string;
	mode: SheetMode;
	ariaLabelledBy: string | undefined;
	value: T;
	setValue: (value: T) => void;
} {
	const domId = useControlDomId(name);
	const mode = useSheetMode();
	const ariaLabelledBy = useCellAriaLabelledBy();
	const [value, setValue] = useField<T>(name, defaultValue);
	return { domId, mode, ariaLabelledBy, value, setValue };
}

/**
 * Row management for a repeater. `rows` is the stored array (never mutated in
 * place — add/remove replace it so subscribers re-render). Row identity for
 * React keys is the caller's concern; the array index is the scope coordinate.
 */
export function useRepeaterRows(name: string): {
	rows: ScopeValues[];
	append: () => void;
	removeAt: (index: number) => void;
	ensureCount: (count: number) => void;
} {
	const store = useSheetStore();
	const path = useScopedPath(name);
	const subscribe = useCallback(
		(cb: () => void) => store.subscribe(path, cb),
		[store, path],
	);
	const rows = useSyncExternalStore(
		subscribe,
		() => (store.get(path) as ScopeValues[] | undefined) ?? EMPTY_ROWS,
	);
	const append = useCallback(() => {
		const cur = (store.get(path) as ScopeValues[] | undefined) ?? [];
		store.set(path, [...cur, {}]);
	}, [store, path]);
	const removeAt = useCallback(
		(index: number) => {
			const cur = (store.get(path) as ScopeValues[] | undefined) ?? [];
			store.set(
				path,
				cur.filter((_, i) => i !== index),
			);
		},
		[store, path],
	);
	const ensureCount = useCallback(
		(count: number) => {
			const cur = (store.get(path) as ScopeValues[] | undefined) ?? [];
			if (cur.length >= count) return;
			store.set(path, [
				...cur,
				...Array.from({ length: count - cur.length }, () => ({}) as ScopeValues),
			]);
		},
		[store, path],
	);
	return { rows, append, removeAt, ensureCount };
}

// Stable empty array so useSyncExternalStore's snapshot doesn't churn when a
// repeater has no stored rows yet.
const EMPTY_ROWS: ScopeValues[] = [];
