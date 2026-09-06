import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Expr } from "./formula";
import { resolveWhen } from "./when-styling";

// A formula error DEV-warns; silence it so only real failures show.
beforeEach(() => {
	vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	vi.restoreAllMocks();
});

const ctx = "text /1/2";
/** Resolver over a fixed value map, matching `evaluate`'s resolver contract. */
const from = (values: Record<string, unknown>) => (ref: string) => values[ref];

describe("resolveWhen — nothing to apply", () => {
	it("returns empty class list and bundle when both are undefined", () => {
		expect(resolveWhen(undefined, undefined, from({}), ctx)).toEqual({
			classes: [],
			styleBundle: {},
		});
	});

	it("returns empty for an empty map / empty array (the truthy branch)", () => {
		expect(resolveWhen({}, [], from({}), ctx)).toEqual({
			classes: [],
			styleBundle: {},
		});
	});
});

describe("resolveWhen — class_when", () => {
	it("includes a class whose condition is truthy, drops a falsy one", () => {
		const { classes } = resolveWhen(
			{
				"is-on": { ref: "on" },
				"is-off": { ref: "off" },
			},
			undefined,
			from({ on: true, off: false }),
			ctx,
		);
		expect(classes).toEqual(["is-on"]);
	});

	it("treats a zero number as falsy and a non-zero as truthy", () => {
		const cw: Record<string, Expr> = {
			zero: { ref: "z" },
			nonzero: { ref: "n" },
		};
		expect(resolveWhen(cw, undefined, from({ z: 0, n: 3 }), ctx).classes).toEqual([
			"nonzero",
		]);
	});

	it("evaluates a comparison formula against the resolver", () => {
		const cw: Record<string, Expr> = {
			high: { op: ">=", args: [{ ref: "score" }, 16] },
		};
		expect(resolveWhen(cw, undefined, from({ score: 16 }), ctx).classes).toEqual([
			"high",
		]);
		expect(resolveWhen(cw, undefined, from({ score: 15 }), ctx).classes).toEqual([]);
	});

	it("keeps only the truthy keys when several are given", () => {
		const { classes } = resolveWhen(
			{ a: true, b: false, c: true },
			undefined,
			from({}),
			ctx,
		);
		expect(classes).toEqual(["a", "c"]);
	});

	it("treats a formula error as falsy, warns with the context, does not throw", () => {
		const bad = { op: "not-an-op", args: [] } as unknown as Expr;
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		expect(resolveWhen({ boom: bad }, undefined, from({}), ctx).classes).toEqual([]);
		expect(warn).toHaveBeenCalledWith(expect.stringContaining(ctx));
	});
});

describe("resolveWhen — style_when", () => {
	it("merges the styles of an entry whose condition is truthy", () => {
		const { styleBundle } = resolveWhen(
			undefined,
			[{ when: { ref: "hurt" }, styles: { color: "red" } }],
			from({ hurt: true }),
			ctx,
		);
		expect(styleBundle).toEqual({ color: "red" });
	});

	it("skips an entry whose condition is falsy", () => {
		const { styleBundle } = resolveWhen(
			undefined,
			[{ when: { ref: "hurt" }, styles: { color: "red" } }],
			from({ hurt: false }),
			ctx,
		);
		expect(styleBundle).toEqual({});
	});

	it("layers multiple active entries, later winning per property", () => {
		const { styleBundle } = resolveWhen(
			undefined,
			[
				{ when: true, styles: { color: "red", padding: "1px" } },
				{ when: true, styles: { color: "blue" } },
			],
			from({}),
			ctx,
		);
		expect(styleBundle).toEqual({ color: "blue", padding: "1px" });
	});
});

describe("resolveWhen — class_when and style_when together", () => {
	it("resolves both from the same scope", () => {
		const result = resolveWhen(
			{ neg: { op: "<", args: [{ ref: "mod" }, 0] } },
			[
				{
					when: { op: ">=", args: [{ ref: "score" }, 16] },
					styles: { "background-color": "#e6f5e6" },
				},
			],
			from({ mod: -1, score: 17 }),
			ctx,
		);
		expect(result).toEqual({
			classes: ["neg"],
			styleBundle: { "background-color": "#e6f5e6" },
		});
	});
});
