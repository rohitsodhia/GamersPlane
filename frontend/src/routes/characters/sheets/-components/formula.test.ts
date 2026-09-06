import { describe, expect, it, vi } from "vitest";
import {
	collectRefs,
	type Expr,
	evaluate,
	FormulaError,
	isOpName,
	type RefResolver,
} from "./formula";

/** A resolver backed by a plain record; unknown names come back `undefined`. */
const from =
	(values: Record<string, unknown>): RefResolver =>
	(name) =>
		values[name];

describe("evaluate — literals & refs", () => {
	it.each([
		[7, 7],
		[true, true],
	])("returns the literal %j unchanged", (input, expected) => {
		expect(evaluate(input, from({}))).toBe(expected);
	});

	it("resolves a ref and coerces a numeric string to a number", () => {
		expect(evaluate({ ref: "score" }, from({ score: "15" }))).toBe(15);
	});

	it("resolves a missing ref to 0", () => {
		expect(evaluate({ ref: "score" }, from({}))).toBe(0);
	});

	it("resolves an empty-string ref to 0", () => {
		expect(evaluate({ ref: "score" }, from({ score: "" }))).toBe(0);
	});

	it("resolves a non-numeric ref to 0", () => {
		expect(evaluate({ ref: "score" }, from({ score: "abc" }))).toBe(0);
	});

	it("coerces a boolean ref to 1 / 0", () => {
		expect(evaluate({ ref: "flag" }, from({ flag: true }))).toBe(1);
		expect(evaluate({ ref: "flag" }, from({ flag: false }))).toBe(0);
	});
});

describe("evaluate — D&D ability modifier (the driving use case)", () => {
	// mod = floor((score - 10) / 2)
	const mod = (): Expr => ({
		op: "floor",
		args: [{ op: "/", args: [{ op: "-", args: [{ ref: "score" }, 10] }, 2] }],
	});

	it.each([
		[10, 0],
		[15, 2],
		[8, -1],
		[1, -5],
	])("score %i -> %i", (score, expected) => {
		expect(evaluate(mod(), from({ score: String(score) }))).toBe(expected);
	});
});

describe("evaluate — arithmetic", () => {
	it.each([
		["+", 6],
		["-", 2],
		["*", 8],
		["/", 2],
		["%", 0],
	] as const)("%s of 4 and 2", (op, expected) => {
		expect(evaluate({ op, args: [4, 2] }, from({}))).toBe(expected);
	});

	it("division by zero yields 0 (not Infinity)", () => {
		expect(evaluate({ op: "/", args: [5, 0] }, from({}))).toBe(0);
	});

	it("modulo by zero yields 0 (not NaN)", () => {
		expect(evaluate({ op: "%", args: [5, 0] }, from({}))).toBe(0);
	});

	it("negates with neg", () => {
		expect(evaluate({ op: "neg", args: [{ ref: "x" }] }, from({ x: "3" }))).toBe(-3);
	});

	it("treats a boolean operand as 1 in an arithmetic context", () => {
		expect(evaluate({ op: "+", args: [true, 1] }, from({}))).toBe(2);
	});
});

describe("evaluate — comparison", () => {
	it.each([
		["==", 2, 2, true],
		["==", 2, 3, false],
		["!=", 2, 3, true],
		["<", 2, 3, true],
		["<", 3, 3, false],
		["<=", 3, 3, true],
		[">", 3, 2, true],
		[">=", 3, 3, true],
	] as const)("%s(%i, %i) -> %s", (op, a, b, expected) => {
		expect(evaluate({ op, args: [a, b] }, from({}))).toBe(expected);
	});
});

describe("evaluate — logical & conditional", () => {
	it("&& returns a boolean, not the operand", () => {
		expect(evaluate({ op: "&&", args: [1, 2] }, from({}))).toBe(true);
	});

	it("|| returns a boolean, not the operand", () => {
		expect(evaluate({ op: "||", args: [0, 5] }, from({}))).toBe(true);
	});

	it("! negates truthiness", () => {
		expect(evaluate({ op: "!", args: [0] }, from({}))).toBe(true);
	});

	it("&& short-circuits: the second arg is not evaluated when the first is falsy", () => {
		const resolve = vi.fn(from({ a: "0", b: "1" }));
		evaluate({ op: "&&", args: [{ ref: "a" }, { ref: "b" }] }, resolve);
		expect(resolve).toHaveBeenCalledWith("a");
		expect(resolve).not.toHaveBeenCalledWith("b");
	});

	it("if selects the then-branch and never touches the else-branch", () => {
		const resolve = vi.fn(from({ cond: "1", yes: "10", no: "99" }));
		const result = evaluate(
			{ op: "if", args: [{ ref: "cond" }, { ref: "yes" }, { ref: "no" }] },
			resolve,
		);
		expect(result).toBe(10);
		expect(resolve).not.toHaveBeenCalledWith("no");
	});

	it("if treats a zero condition as falsy", () => {
		expect(evaluate({ op: "if", args: [0, 1, 2] }, from({}))).toBe(2);
	});

	it("models 'proficient save bonus' — if(prof, mod + profBonus, mod)", () => {
		const expr: Expr = {
			op: "if",
			args: [
				{ ref: "prof" },
				{ op: "+", args: [{ ref: "mod" }, { ref: "profBonus" }] },
				{ ref: "mod" },
			],
		};
		expect(evaluate(expr, from({ prof: true, mod: "3", profBonus: "2" }))).toBe(5);
		expect(evaluate(expr, from({ prof: false, mod: "3", profBonus: "2" }))).toBe(3);
	});
});

describe("evaluate — numeric functions", () => {
	it.each([
		["floor", [2.9], 2],
		["ceil", [2.1], 3],
		["round", [2.5], 3],
		["abs", [-4], 4],
		["min", [3, 1, 2], 1],
		["max", [3, 1, 2], 3],
		["sum", [1, 2, 3, 4], 10],
	] as const)("%s(%j) -> %i", (op, args, expected) => {
		expect(evaluate({ op, args: [...args] }, from({}))).toBe(expected);
	});

	it("clamp keeps a value inside [lo, hi]", () => {
		expect(evaluate({ op: "clamp", args: [5, 0, 3] }, from({}))).toBe(3);
		expect(evaluate({ op: "clamp", args: [-5, 0, 3] }, from({}))).toBe(0);
		expect(evaluate({ op: "clamp", args: [2, 0, 3] }, from({}))).toBe(2);
	});

	it("sum of no args is 0", () => {
		expect(evaluate({ op: "sum", args: [] }, from({}))).toBe(0);
	});
});

describe("evaluate — malformed trees throw FormulaError", () => {
	it("unknown op", () => {
		expect(() => evaluate({ op: "pow" as never, args: [2, 3] }, from({}))).toThrow(
			FormulaError,
		);
	});

	it("wrong fixed arity", () => {
		expect(() => evaluate({ op: "floor", args: [1, 2] }, from({}))).toThrow(
			FormulaError,
		);
	});

	it("below minimum arity", () => {
		expect(() => evaluate({ op: "min", args: [] }, from({}))).toThrow(FormulaError);
	});

	it("a node that is neither literal, ref, nor op", () => {
		expect(() => evaluate({ foo: "bar" } as never, from({}))).toThrow(FormulaError);
	});

	it("null in operand position", () => {
		expect(() => evaluate(null as never, from({}))).toThrow(FormulaError);
	});
});

describe("collectRefs", () => {
	it("returns refs in first-encounter order without duplicates", () => {
		const expr: Expr = {
			op: "+",
			args: [{ ref: "b" }, { op: "*", args: [{ ref: "a" }, { ref: "b" }] }],
		};
		expect(collectRefs(expr)).toEqual(["b", "a"]);
	});

	it("returns an empty array for a literal-only formula", () => {
		expect(collectRefs({ op: "+", args: [1, 2] })).toEqual([]);
	});
});

describe("isOpName", () => {
	it("accepts a whitelisted op and rejects anything else", () => {
		expect(isOpName("clamp")).toBe(true);
		expect(isOpName("system")).toBe(false);
	});
});
