import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Expr } from "./formula";
import { computeLoopIterations, MAX_LOOP_ITERATIONS, resolveLoopCount } from "./Loop";

// A malformed formula / both-forms / neither-form all DEV-warn; silence them so
// only real failures surface.
beforeEach(() => {
	vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	vi.restoreAllMocks();
});

const ctx = "loop /3";
const from = (values: Record<string, unknown>) => (ref: string) => values[ref];
const noRefs = from({});

describe("resolveLoopCount", () => {
	it("passes a literal integer through", () => {
		expect(resolveLoopCount(5, noRefs, ctx)).toBe(5);
	});

	it("floors a fractional count", () => {
		expect(resolveLoopCount(3.9, noRefs, ctx)).toBe(3);
	});

	it("treats zero and negatives as 0", () => {
		expect(resolveLoopCount(0, noRefs, ctx)).toBe(0);
		expect(resolveLoopCount(-4, noRefs, ctx)).toBe(0);
	});

	it("clamps to MAX_LOOP_ITERATIONS", () => {
		expect(resolveLoopCount(5000, noRefs, ctx)).toBe(MAX_LOOP_ITERATIONS);
	});

	it("treats a non-finite formula result as 0", () => {
		// Overflows to Infinity without throwing — hits the !Number.isFinite guard,
		// a different path than the malformed-formula catch below.
		const expr: Expr = { op: "*", args: [1e308, 10] };
		expect(resolveLoopCount(expr, noRefs, ctx)).toBe(0);
	});

	it("evaluates a formula count against the resolver", () => {
		const expr: Expr = { op: "+", args: [{ ref: "base" }, 1] };
		expect(resolveLoopCount(expr, from({ base: 4 }), ctx)).toBe(5);
	});

	it("returns 0 and warns for a malformed formula", () => {
		const bad = { op: "nope", args: [] } as unknown as Expr;
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		expect(resolveLoopCount(bad, noRefs, ctx)).toBe(0);
		expect(warn).toHaveBeenCalledWith(expect.stringContaining(ctx));
	});
});

describe("computeLoopIterations — items form", () => {
	it("yields one iteration per entry, index in order, item attached", () => {
		const items = [{ label: "a" }, { label: "b" }, { label: "c" }];
		expect(computeLoopIterations({ items }, noRefs, ctx)).toEqual([
			{ index: 0, item: { label: "a" } },
			{ index: 1, item: { label: "b" } },
			{ index: 2, item: { label: "c" } },
		]);
	});

	it("ignores count (and warns) when both are set", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const out = computeLoopIterations({ items: [{ x: 1 }], count: 9 }, noRefs, ctx);
		expect(out).toEqual([{ index: 0, item: { x: 1 } }]);
		expect(warn).toHaveBeenCalledWith(expect.stringContaining(ctx));
	});

	it("caps a long items array at MAX_LOOP_ITERATIONS", () => {
		const items = Array.from({ length: MAX_LOOP_ITERATIONS + 25 }, (_, i) => ({ i }));
		expect(computeLoopIterations({ items }, noRefs, ctx)).toHaveLength(
			MAX_LOOP_ITERATIONS,
		);
	});
});

describe("computeLoopIterations — count form", () => {
	it("yields N index-only iterations", () => {
		expect(computeLoopIterations({ count: 3 }, noRefs, ctx)).toEqual([
			{ index: 0, item: null },
			{ index: 1, item: null },
			{ index: 2, item: null },
		]);
	});

	it("renders nothing and warns when neither items nor count is set", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		expect(computeLoopIterations({}, noRefs, ctx)).toEqual([]);
		expect(warn).toHaveBeenCalledWith(expect.stringContaining(ctx));
	});
});
