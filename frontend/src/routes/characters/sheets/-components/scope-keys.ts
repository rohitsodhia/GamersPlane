// Maps each field `name` in one value scope to where its value is stored: the
// field's server-minted `id` (see `BaseElement.id`), plus — for a `grid` — its
// rows and each row's own scope, so a ref path can walk into it.
//
// Values are stored by id, not name, so renaming a field in the sheet doesn't
// orphan what characters already typed into it. Authors (and formulas,
// `on_click.set`, component bindings) still address fields by `name`; this map
// is the one place a name becomes a store key.
//
// A scope is the root of the sheet, one repeater row template, or one grid row.
// Its fields are the value-bearing nodes reachable without crossing into a
// nested repeater's rows or grid's rows — a `repeater` / `grid` itself is a
// field of the enclosing scope (it owns one array / object there), but its
// row fields belong to the row's own scope.

import type { GridElement, SheetElement } from "./types";

/** One grid row: its store key and the scope its cells' fields live in. */
export interface GridRowEntry {
	id: string;
	scope: ScopeKeys;
}

/** What a `name` in a scope refers to. */
export type FieldEntry =
	| { kind: "value"; id: string }
	| { kind: "repeater"; id: string }
	| { kind: "grid"; id: string; rows: ReadonlyMap<string, GridRowEntry> };

/** `name` → field, for one scope. */
export type ScopeKeys = ReadonlyMap<string, FieldEntry>;

/** Scalar field types; each stores one value under its own key. */
const SCALAR_FIELD_TYPES = new Set(["input", "textarea", "select", "checkbox"]);

function isValueNode(node: SheetElement): node is SheetElement & { name: string } {
	if (typeof (node as { name?: unknown }).name !== "string") return false;
	if (SCALAR_FIELD_TYPES.has(node.type)) return true;
	if (node.type === "repeater" || node.type === "grid") return true;
	return node.type === "text" && node.formula != null;
}

/** A grid's rows, keyed by their author-facing `key`, in either authoring form. */
function gridRows(node: GridElement): Map<string, GridRowEntry> {
	const rows = new Map<string, GridRowEntry>();
	if (node.items != null) {
		const scope = scopeKeysFor(node.row ?? NO_NODES);
		for (const item of node.items) {
			rows.set(item.key, { id: item.id || item.key, scope });
		}
		return rows;
	}
	for (const c of node.content ?? []) {
		if (c.type === "grid_row") {
			rows.set(c.key, { id: c.id || c.key, scope: scopeKeysFor(c.content) });
		}
	}
	return rows;
}

function fieldEntry(node: SheetElement & { name: string }, id: string): FieldEntry {
	if (node.type === "repeater") return { kind: "repeater", id };
	if (node.type === "grid") return { kind: "grid", id, rows: gridRows(node) };
	return { kind: "value", id };
}

/**
 * Child node lists that render in the SAME scope as `node`. A repeater's rows
 * and a grid's rows are their own scopes, so only their headers (rendered
 * once, outside any row) stay in this one.
 */
function sameScopeChildren(node: SheetElement): SheetElement[][] {
	if (node.type === "repeater") return node.header ? [node.header] : [];
	if (node.type === "grid") {
		const lists: SheetElement[][] = [];
		if (node.header) lists.push(node.header);
		for (const c of node.content ?? []) {
			if (c.type === "grid_header") lists.push(c.content);
		}
		return lists;
	}
	const content = (node as { content?: unknown }).content;
	return Array.isArray(content) ? [content as SheetElement[]] : [];
}

function collect(nodes: readonly SheetElement[], keys: Map<string, FieldEntry>): void {
	for (const node of nodes) {
		if (isValueNode(node)) {
			if (keys.has(node.name)) {
				if (import.meta.env.DEV) {
					console.warn(
						`[sheet] duplicate field name "${node.name}" in one scope; the first one wins`,
					);
				}
			} else {
				if (!node.id && import.meta.env.DEV) {
					console.warn(
						`[sheet] field "${node.name}" has no id; storing its value under its name`,
					);
				}
				keys.set(node.name, fieldEntry(node, node.id || node.name));
			}
		}
		for (const children of sameScopeChildren(node)) collect(children, keys);
	}
}

const NO_NODES: readonly SheetElement[] = [];

// Keyed on the template array itself: schema nodes are stable for as long as
// the schema is, so every row of a repeater / grid shares one map, and the map
// (a context value) keeps its identity across renders.
const cache = new WeakMap<readonly SheetElement[], ScopeKeys>();

/** The `name` → field map for the scope whose top-level nodes are `nodes`. */
export function scopeKeysFor(nodes: readonly SheetElement[]): ScopeKeys {
	let keys = cache.get(nodes);
	if (keys == null) {
		const built = new Map<string, FieldEntry>();
		collect(nodes, built);
		keys = built;
		cache.set(nodes, keys);
	}
	return keys;
}

/** The store key for `name` in a scope: its id, or the name itself if unknown. */
export function storeKey(keys: ScopeKeys, name: string): string {
	return keys.get(name)?.id ?? name;
}
