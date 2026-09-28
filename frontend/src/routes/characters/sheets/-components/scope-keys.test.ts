import { afterEach, describe, expect, it, vi } from "vitest";
import { type ScopeKeys, scopeKeysFor, storeKey } from "./scope-keys";
import type { SheetElement } from "./types";

const nodes = (list: unknown[]) => list as SheetElement[];

/** `name` -> id, for comparing a scope's map against a plain object. */
const ids = (keys: ScopeKeys) =>
	Object.fromEntries([...keys].map(([name, entry]) => [name, entry.id]));

afterEach(() => {
	vi.restoreAllMocks();
});

describe("scopeKeysFor", () => {
	it("maps each value-bearing field's name to its id, skipping non-value nodes", () => {
		const keys = scopeKeysFor(
			nodes([
				{ type: "input", name: "name", id: "a1" },
				{ type: "textarea", name: "notes", id: "a2" },
				{ type: "select", name: "size", id: "a3", values: [] },
				{ type: "checkbox", name: "inspired", id: "a4" },
				{ type: "text", name: "total", id: "a5", formula: 1 },
				{ type: "text", name: "label", text: "literal" },
				{ type: "collapsible", name: "gm", content: [] },
			]),
		);
		expect(ids(keys)).toEqual({
			name: "a1",
			notes: "a2",
			size: "a3",
			inspired: "a4",
			total: "a5",
		});
	});

	it("includes fields nested in transparent containers", () => {
		const keys = scopeKeysFor(
			nodes([
				{
					type: "section",
					content: [
						{ type: "group", content: [{ type: "input", name: "a", id: "i1" }] },
						{
							type: "list",
							variant: "ordered",
							content: [
								{
									type: "loop",
									count: 2,
									content: [{ type: "input", name: "b", id: "i2" }],
								},
							],
						},
						{
							type: "collapsible",
							name: "c",
							content: [{ type: "input", name: "c", id: "i3" }],
						},
					],
				},
			]),
		);
		expect(ids(keys)).toEqual({ a: "i1", b: "i2", c: "i3" });
	});

	it("maps a repeater / grid itself but not its row fields, and includes header fields", () => {
		const keys = scopeKeysFor(
			nodes([
				{
					type: "repeater",
					name: "classes",
					id: "r1",
					header: [{ type: "input", name: "rep_head", id: "h1" }],
					content: [{ type: "input", name: "level", id: "x1" }],
				},
				{
					type: "grid",
					name: "stats",
					id: "g1",
					items: [{ key: "str", label: "STR", id: "row1" }],
					header: [{ type: "input", name: "grid_head", id: "h2" }],
					row: [{ type: "input", name: "score", id: "x2" }],
				},
				{
					type: "grid",
					name: "saves",
					id: "g2",
					content: [
						{
							type: "grid_header",
							content: [{ type: "input", name: "explicit_head", id: "h3" }],
						},
						{
							type: "grid_row",
							key: "fort",
							id: "row2",
							content: [{ type: "input", name: "bonus", id: "x3" }],
						},
					],
				},
			]),
		);
		expect(ids(keys)).toEqual({
			classes: "r1",
			rep_head: "h1",
			stats: "g1",
			grid_head: "h2",
			saves: "g2",
			explicit_head: "h3",
		});
	});

	it("falls back to the name for a field with no id, and warns", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const keys = scopeKeysFor(nodes([{ type: "input", name: "legacy" }]));
		expect(storeKey(keys, "legacy")).toBe("legacy");
		expect(warn).toHaveBeenCalledOnce();
	});

	it("keeps the first of two same-named fields, and warns", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const keys = scopeKeysFor(
			nodes([
				{ type: "input", name: "dup", id: "first" },
				{ type: "input", name: "dup", id: "second" },
			]),
		);
		expect(storeKey(keys, "dup")).toBe("first");
		expect(warn).toHaveBeenCalledOnce();
	});

	it("returns the same map for the same node array", () => {
		const template = nodes([{ type: "input", name: "a", id: "i1" }]);
		expect(scopeKeysFor(template)).toBe(scopeKeysFor(template));
	});
});

describe("storeKey", () => {
	it("uses the name itself for a name the scope doesn't know", () => {
		const keys = scopeKeysFor(nodes([{ type: "input", name: "a", id: "i1" }]));
		expect(storeKey(keys, "unknown")).toBe("unknown");
	});
});
