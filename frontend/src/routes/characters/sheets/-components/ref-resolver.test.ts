import { describe, expect, it } from "vitest";
import { createRefResolver } from "./loop-context";
import { scopeKeysFor } from "./scope-keys";
import type { Path, Scope } from "./sheet-values";
import type { SheetElement } from "./types";

/** A root scope over one `input` named `hp` with id `f1`. */
const ROOT_KEYS = scopeKeysFor([
	{ type: "input", name: "hp", id: "f1" },
] as SheetElement[]);
const ROOT: Scope = { path: [], keys: ROOT_KEYS, root: ROOT_KEYS };

/** A stub store `get` that records the paths it was asked for. */
function fakeGet(values: Record<string, unknown> = {}) {
	const calls: Path[] = [];
	const get = (path: Path) => {
		calls.push(path);
		return values[path.join(".")];
	};
	return { get, calls };
}

describe("createRefResolver", () => {
	it("resolves $index to the loop index", () => {
		const { get } = fakeGet();
		const resolve = createRefResolver(get, ROOT, { index: 3, item: null });
		expect(resolve("$index")).toBe(3);
	});

	it("resolves $index to 0 outside any loop", () => {
		const { get } = fakeGet();
		expect(createRefResolver(get, ROOT, null)("$index")).toBe(0);
	});

	it("reads $item.<key> from the current loop item, never the store", () => {
		const { get, calls } = fakeGet({ label: "from-store" });
		const resolve = createRefResolver(get, ROOT, {
			index: 0,
			item: { label: "from-item" },
		});
		expect(resolve("$item.label")).toBe("from-item");
		expect(resolve("$item.missing")).toBeUndefined();
		// A `count` loop has no item.
		const countLoop = createRefResolver(get, ROOT, { index: 0, item: null });
		expect(countLoop("$item.label")).toBeUndefined();
		expect(calls).toHaveLength(0);
	});

	it("reads a $(inner) segment through itself, loop refs included", () => {
		const keys = scopeKeysFor([
			{ type: "select", name: "pick", id: "p1", values: ["str", "dex"] },
			{
				type: "grid",
				name: "stats",
				id: "g1",
				items: [
					{ key: "str", label: "STR", id: "r1" },
					{ key: "dex", label: "DEX", id: "r2" },
				],
				row: [{ type: "input", name: "score", id: "s1" }],
			},
		] as SheetElement[]);
		const scope: Scope = { path: [], keys, root: keys };
		const { get } = fakeGet({ p1: "str", "g1.r1.s1": 14, "g1.r2.s1": 12 });

		const resolve = createRefResolver(get, scope, { index: 0, item: { stat: "dex" } });

		expect(resolve("stats.$(pick).score")).toBe(14);
		expect(resolve("stats.$($item.stat).score")).toBe(12);
	});

	it("reads the store only at a resolved path", () => {
		const { get, calls } = fakeGet({ f1: 15, nope: "x", $weird: "y" });
		const resolve = createRefResolver(get, ROOT, null);
		expect(resolve("nope")).toBeUndefined();
		expect(resolve("$weird")).toBeUndefined();
		expect(calls).toHaveLength(0);
		expect(resolve("hp")).toBe(15);
		expect(calls).toEqual([["f1"]]);
	});
});
