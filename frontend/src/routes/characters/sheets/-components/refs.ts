// Resolves a formula `ref` (or a button's `on_click.set`) to the store path of
// the value it names.
//
// Ref syntax — every ref is a dotted path of field `name`s / grid row `key`s:
//   - `stats.str.mod`   absolute, from the sheet root: the `stats` grid, its
//                       `str` row, that row's `mod` field. A single segment
//                       (`harm`) is just a root-level field — there is no
//                       "nearest scope" lookup; a bare name always means the root.
//   - `$row.score`      relative to the current repeater / grid row (the row the
//                       formula sits in); may continue into a grid nested there.
//   - `$item.label`     a key of the enclosing `loop`'s current `items` entry —
//                       author data, not the store (see `createRefResolver`).
//   - `$index`          the enclosing `loop`'s 0-based iteration (not the store).
//
// Any segment of a store path (not of `$item.…`) may instead be a dynamic
// `$(inner)`: `inner` is a ref, resolved first, and its value is used as that
// segment's name — `stats.$($row.stat).mod` reads the `mod` of whichever
// `stats` row the row's `stat` select names. It must be a whole segment, can't
// nest, and a value that isn't a non-empty string resolves the ref to
// `undefined`. A dynamic segment is always a name, never `$row`.
//
// A path must end on a scalar field. Pointing at a whole grid / grid row, into
// a repeater (whose rows are runtime-managed, so there's no fixed row to name),
// or at anything unknown resolves to `undefined` — never throws — and
// `evaluate` coerces that to 0.
//
// The API rejects a publish whose refs don't resolve by these same rules
// (`api/src/app/character_sheets/layout_refs.py`); keep the two in sync.

import type { RefResolver } from "./formula";
import type { ScopeKeys } from "./scope-keys";
import type { Path, Scope } from "./sheet-values";

/** One ref segment: a literal name, or a `$(inner)` to resolve first. */
type Segment = { name: string } | { inner: string };

/** `ref`'s segments, or `undefined` if it's malformed. */
function splitRef(ref: string): Segment[] | undefined {
	const segments: Segment[] = [];
	let i = 0;
	while (true) {
		if (ref.startsWith("$(", i)) {
			const close = ref.indexOf(")", i);
			if (close === -1) return undefined;
			const inner = ref.slice(i + 2, close);
			if (inner === "" || inner.includes("$(")) return undefined;
			segments.push({ inner });
			i = close + 1;
			if (i === ref.length) return segments;
			// `$(…)` must be the whole segment.
			if (ref[i] !== ".") return undefined;
		} else {
			const dot = ref.indexOf(".", i);
			const name = ref.slice(i, dot === -1 ? undefined : dot);
			if (name === "" || name.includes("$(")) return undefined;
			segments.push({ name });
			if (dot === -1) return segments;
			i = dot;
		}
		i += 1;
	}
}

/** Walks `segments` from the scope `keys` stored at `base`. */
function walk(keys: ScopeKeys, base: Path, segments: string[]): Path | undefined {
	const [head, ...rest] = segments;
	const entry = keys.get(head);
	if (entry == null) return undefined;
	if (rest.length === 0) {
		return entry.kind === "value" ? [...base, entry.id] : undefined;
	}
	if (entry.kind !== "grid") return undefined;
	const [rowKey, ...inRow] = rest;
	const row = entry.rows.get(rowKey);
	if (row == null || inRow.length === 0) return undefined;
	return walk(row.scope, [...base, entry.id, row.id], inRow);
}

/**
 * The store path `ref` points at, from `scope`, or `undefined` when it names no
 * scalar field (including the store-less `$index` / `$item.*`). `resolve`
 * reads a dynamic segment's inner ref; without it, a dynamic ref is
 * `undefined`.
 */
export function resolveRefPath(
	ref: string,
	scope: Scope,
	resolve?: RefResolver,
): Path | undefined {
	const segments = splitRef(ref);
	if (segments === undefined) return undefined;
	const names: string[] = [];
	for (const segment of segments) {
		const name = "name" in segment ? segment.name : resolve?.(segment.inner);
		if (typeof name !== "string" || name === "") return undefined;
		names.push(name);
	}
	const head = segments[0];
	if ("name" in head && head.name === "$row") {
		// At the sheet root there is no enclosing row.
		if (scope.path.length === 0 || names.length === 1) return undefined;
		return walk(scope.keys, scope.path, names.slice(1));
	}
	if (names[0].startsWith("$")) return undefined;
	return walk(scope.root, [], names);
}
