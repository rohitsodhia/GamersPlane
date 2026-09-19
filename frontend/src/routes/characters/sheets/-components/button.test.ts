import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resolveClickValue } from "./Button";
import type { Expr } from "./formula";

// A malformed formula DEV-warns; silence it so only real failures surface.
beforeEach(() => {
	vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	vi.restoreAllMocks();
});

const ctx = 'button "seg"';
const from = (values: Record<string, unknown>) => (ref: string) => values[ref];
const noRefs = from({});

describe("resolveClickValue", () => {
	it("passes a literal `to` through (Reset button: to = 0)", () => {
		expect(resolveClickValue(0, noRefs, ctx)).toBe(0);
	});

	it("evaluates `$index + 1` against the resolver (fill up to segment N)", () => {
		const to: Expr = { op: "+", args: [{ ref: "$index" }, 1] };
		expect(resolveClickValue(to, from({ $index: 3 }), ctx)).toBe(4);
	});

	it("passes a boolean result through (toggle a flag)", () => {
		const to: Expr = { op: "!", args: [{ ref: "flag" }] };
		expect(resolveClickValue(to, from({ flag: false }), ctx)).toBe(true);
	});

	it("returns undefined and warns on a malformed formula (click is a no-op)", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const bad = { op: "bogus", args: [] } as unknown as Expr;
		expect(resolveClickValue(bad, noRefs, ctx)).toBeUndefined();
		expect(warn).toHaveBeenCalledWith(expect.stringContaining(ctx));
	});
});
