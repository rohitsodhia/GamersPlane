import { describe, expect, it } from "vitest";
import {
	applyAdvantage,
	buildRoll,
	diceError,
	isInteractiveTarget,
	normalizeDice,
	parseTemplate,
	TemplateError,
} from "./roll";
import type { RollSpec } from "./types";

const from = (values: Record<string, unknown>) => (ref: string) => values[ref];

function built(spec: RollSpec, values: Record<string, unknown> = {}, fallback = "") {
	const result = buildRoll(spec, from(values), fallback);
	if ("error" in result) throw new Error(`expected a roll, got: ${result.error}`);
	return result;
}

function errorOf(spec: RollSpec, values: Record<string, unknown> = {}) {
	const result = buildRoll(spec, from(values), "");
	if (!("error" in result)) throw new Error(`expected an error, got: ${result.dice}`);
	return result.error;
}

describe("parseTemplate", () => {
	it("splits literal text and refs", () => {
		expect(parseTemplate("1d20+${str_mod} x")).toEqual([
			{ text: "1d20+" },
			{ ref: "str_mod" },
			{ text: " x" },
		]);
	});

	it("keeps a dynamic $(…) ref, with its parens and dots, whole", () => {
		expect(parseTemplate("${stats.$(pick).mod}${$row.bonus}")).toEqual([
			{ ref: "stats.$(pick).mod" },
			{ ref: "$row.bonus" },
		]);
	});

	it("rejects an unterminated or empty placeholder", () => {
		expect(() => parseTemplate("1d${x")).toThrow(TemplateError);
		expect(() => parseTemplate("1d${stats.$(pick}")).toThrow(TemplateError);
		expect(() => parseTemplate("1d${ }")).toThrow(TemplateError);
	});
});

describe("buildRoll dice", () => {
	it("substitutes refs, truncating numbers and reading numeric text", () => {
		expect(
			built({ dice: "${n}d${die}+${mod}" }, { n: 2.9, die: "8", mod: -1 }).dice,
		).toBe("2d8-1");
	});

	it("substitutes a boolean as 1 or 0, and a missing or empty value as 0", () => {
		expect(built({ dice: "${a}d6+${b}+${c}d8" }, { a: true, c: 1 }).dice).toBe(
			"1d6+1d8",
		);
		expect(built({ dice: "1d20+${gone}+${blank}" }, { blank: "" }).dice).toBe("1d20");
	});

	it("errors on a non-numeric text value, naming the ref and value", () => {
		expect(errorOf({ dice: "1d20+${x}" }, { x: "abc" })).toBe(
			"${x} is 'abc', not a number",
		);
		expect(errorOf({ dice: "1d20+${x}" }, { x: { type: "doc" } })).toContain(
			"not a number",
		);
	});

	it("errors on a malformed template", () => {
		expect(errorOf({ dice: "1d${x" })).toContain("unterminated");
		expect(errorOf({ dice: "1d${}" })).toContain("empty");
	});

	it("errors when the substituted string isn't valid dice", () => {
		expect(errorOf({ dice: "1d${die}" }, { die: 0 })).toContain("d0");
		expect(errorOf({ dice: "${n}d6" }, { n: 0 })).toContain("0 dice");
	});

	it("passes mode through, defaulting to new", () => {
		expect(built({ dice: "1d20" }).mode).toBe("new");
		expect(built({ dice: "1d20", mode: "add" }).mode).toBe("add");
	});
});

describe("normalizeDice (sign sugar)", () => {
	it.each([
		["1d20+-3", "1d20-3"],
		["1d20-+3", "1d20-3"],
		["1d20--3", "1d20+3"],
		["1d20++3", "1d20+3"],
		["1d20 + 5", "1d20+5"],
		["1d20+0", "1d20"],
		["1d20-0", "1d20"],
		["1d20+-0", "1d20"],
		["1d20+0,1d6-0", "1d20,1d6"],
		["+1d20", "1d20"],
		["1d6,+1d4", "1d6,1d4"],
	])("%s -> %s", (input, expected) => {
		expect(normalizeDice(input)).toBe(expected);
	});

	it("keeps zeros that aren't a bare modifier term", () => {
		expect(normalizeDice("1d20+0d6")).toBe("1d20+0d6");
		expect(normalizeDice("1d10+10")).toBe("1d10+10");
		expect(normalizeDice("1d20+05")).toBe("1d20+05");
	});

	it("applies to substituted values, so a negative modifier reads naturally", () => {
		expect(built({ dice: "1d20-${m}" }, { m: -2 }).dice).toBe("1d20+2");
		expect(built({ dice: "1d20+${m}" }, { m: 0 }).dice).toBe("1d20");
	});
});

describe("buildRoll reason", () => {
	it("falls back to the element's text when the spec has no reason", () => {
		expect(buildRoll({ dice: "1d20" }, from({}), "Athletics")).toMatchObject({
			reason: "Athletics",
		});
	});

	it("substitutes refs, reading text and numbers and treating missing as empty", () => {
		const spec: RollSpec = {
			dice: "1d20",
			reason: "Attack with ${weapon} #${n}${gone}",
		};
		expect(built(spec, { weapon: "Longsword", n: 2 }).reason).toBe(
			"Attack with Longsword #2",
		);
	});

	it("keeps an explicitly empty reason empty rather than using the fallback", () => {
		expect(built({ dice: "1d20", reason: "" }, {}, "Athletics").reason).toBe("");
	});

	it("trims and caps the reason at 100 characters", () => {
		const reason = built({ dice: "1d20", reason: `  ${"x".repeat(150)}` }).reason;
		expect(reason).toBe("x".repeat(100));
	});

	it("errors on a malformed reason template", () => {
		expect(errorOf({ dice: "1d20", reason: "oops ${x" })).toContain("unterminated");
	});
});

describe("diceError (mirror of the basic roller's grammar)", () => {
	it.each([
		"1d20",
		"d20",
		"2d6+3",
		"4d6h3",
		"2D20L1",
		"1d8,1d6",
		"1d20 + 5",
		"100d1000",
		"5",
		"1d6+1d4+2",
	])("accepts %s", (dice) => {
		expect(diceError(dice)).toBeNull();
	});

	it.each([
		["", "no dice"],
		["1d20+", "valid dice expression"],
		["1d-3", "valid dice expression"],
		["0d6", "rolls 0 dice"],
		["101d6", "rolls 101 dice"],
		["1d1", "d1"],
		["1d1001", "d1001"],
	])("rejects %j", (dice, message) => {
		expect(diceError(dice)).toContain(message);
	});
});

describe("advantage", () => {
	it("rewrites only the first single d20 term for advantage / disadvantage", () => {
		expect(applyAdvantage("1d20+5", "advantage")).toBe("2d20h1+5");
		expect(applyAdvantage("d20+5", "disadvantage")).toBe("2d20l1+5");
		expect(applyAdvantage("1d20+1d20", "advantage")).toBe("2d20h1+1d20");
		expect(applyAdvantage("1d6,1d20", "advantage")).toBe("1d6,2d20h1");
	});

	it("leaves the dice alone for a normal roll", () => {
		expect(applyAdvantage("1d20+5", "normal")).toBe("1d20+5");
	});

	it("does not mistake 11d20, 1d200 or an already-kept d20 for a single d20", () => {
		expect(applyAdvantage("11d20", "advantage")).toBe("11d20");
		expect(applyAdvantage("1d200", "advantage")).toBe("1d200");
		expect(applyAdvantage("1d20h1", "advantage")).toBe("1d20h1");
	});

	it("builds with advantage when a single d20 is present, leaving dice in normal form", () => {
		expect(built({ dice: "1d20+${m}", advantage: true }, { m: 3 })).toMatchObject({
			dice: "1d20+3",
			advantage: true,
		});
	});

	it("finds a d20 produced by a substituted ref, and errors when the values give none", () => {
		expect(built({ dice: "${n}d20", advantage: true }, { n: 1 }).dice).toBe("1d20");
		expect(errorOf({ dice: "${n}d20", advantage: true }, { n: 3 })).toContain(
			"single d20",
		);
	});
});

describe("isInteractiveTarget", () => {
	function tree() {
		const root = document.createElement("div");
		root.innerHTML = `
			<span id="plain">text</span>
			<button id="btn"><b id="inbtn">x</b></button>
			<a id="link" href="/x">go</a>
			<input id="inp" />
			<label id="lbl" for="inp">L</label>
		`;
		document.body.append(root);
		return root;
	}
	const at = (root: Element, id: string) => root.querySelector(`#${id}`);

	it("ignores plain content, non-element targets, and an interactive boundary itself", () => {
		const root = tree();
		expect(isInteractiveTarget(at(root, "plain"), root)).toBe(false);
		expect(isInteractiveTarget(null, root)).toBe(false);
		root.setAttribute("role", "button");
		expect(isInteractiveTarget(root, root)).toBe(false);
		expect(isInteractiveTarget(at(root, "plain"), root)).toBe(false);
		root.remove();
	});

	it("flags a button, a link, an input, and anything nested inside a button", () => {
		const root = tree();
		for (const id of ["btn", "inbtn", "link", "inp"]) {
			expect(isInteractiveTarget(at(root, id), root)).toBe(true);
		}
		root.remove();
	});

	it("does not flag a label (it titles the row being rolled)", () => {
		const root = tree();
		expect(isInteractiveTarget(at(root, "lbl"), root)).toBe(false);
		root.remove();
	});

	it("does not count an interactive ancestor outside the boundary", () => {
		const outer = document.createElement("button");
		const root = document.createElement("div");
		outer.append(root);
		document.body.append(outer);
		expect(isInteractiveTarget(root, root)).toBe(false);
		outer.remove();
	});
});
