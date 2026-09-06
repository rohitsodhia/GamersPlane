import { describe, expect, it } from "vitest";
import { createRefResolver } from "./loop-context";
import type { Path } from "./sheet-values";

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
		const resolve = createRefResolver(get, ["stats"], { index: 3, item: null });
		expect(resolve("$index")).toBe(3);
	});

	it("resolves $index to 0 outside any loop", () => {
		const { get } = fakeGet();
		expect(createRefResolver(get, [], null)("$index")).toBe(0);
	});

	it("never sends a $-prefixed name to the store", () => {
		const { get, calls } = fakeGet({ $weird: "x" });
		expect(createRefResolver(get, [], null)("$weird")).toBeUndefined();
		expect(calls).toHaveLength(0);
	});

	it("reads a field from the current loop item before the store", () => {
		const { get, calls } = fakeGet({ label: "from-store" });
		const resolve = createRefResolver(get, [], {
			index: 0,
			item: { label: "from-item" },
		});
		expect(resolve("label")).toBe("from-item");
		expect(calls).toHaveLength(0);
	});

	it("falls through to the store, scoped by the prefix, for a plain ref", () => {
		const { get, calls } = fakeGet({ "stats.str.score": 15 });
		const resolve = createRefResolver(get, ["stats", "str"], {
			index: 0,
			item: { other: 1 },
		});
		expect(resolve("score")).toBe(15);
		expect(calls).toEqual([["stats", "str", "score"]]);
	});
});
