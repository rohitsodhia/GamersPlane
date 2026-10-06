import { describe, expect, it } from "vitest";
import { resolveRefPath } from "./refs";
import { scopeKeysFor } from "./scope-keys";
import type { Scope } from "./sheet-values";
import type { SheetElement } from "./types";

// Repeater row template: a scalar plus a nested (compact) grid.
const REPEATER_ROW = [
	{ type: "input", name: "level", id: "l1" },
	{
		type: "grid",
		name: "sub",
		id: "g3",
		items: [{ key: "a", label: "A", id: "ra" }],
		row: [{ type: "input", name: "x", id: "x1" }],
	},
] as SheetElement[];

const ROOT_NODES = [
	{ type: "input", name: "hp", id: "f1" },
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
	{
		type: "grid",
		name: "saves",
		id: "g2",
		content: [
			{
				type: "grid_row",
				key: "fort",
				id: "rf",
				content: [{ type: "input", name: "bonus", id: "b1" }],
			},
		],
	},
	{ type: "repeater", name: "classes", id: "rp1", content: REPEATER_ROW },
] as SheetElement[];

const root = scopeKeysFor(ROOT_NODES);
const ROOT: Scope = { path: [], keys: root, root };
const IN_REPEATER_ROW: Scope = {
	path: ["rp1", 0],
	keys: scopeKeysFor(REPEATER_ROW),
	root,
};

describe("resolveRefPath", () => {
	it("resolves a single segment to a root-level field", () => {
		expect(resolveRefPath("hp", ROOT)).toEqual(["f1"]);
	});

	it("treats a single segment as root-level even from inside a row", () => {
		expect(resolveRefPath("hp", IN_REPEATER_ROW)).toEqual(["f1"]);
		expect(resolveRefPath("level", IN_REPEATER_ROW)).toBeUndefined();
	});

	it("walks into a compact-form grid row by its key", () => {
		expect(resolveRefPath("stats.dex.score", ROOT)).toEqual(["g1", "r2", "s1"]);
	});

	it("walks into an explicit-form grid row by its key", () => {
		expect(resolveRefPath("saves.fort.bonus", ROOT)).toEqual(["g2", "rf", "b1"]);
	});

	it("resolves $row.<name> from the current row", () => {
		expect(resolveRefPath("$row.level", IN_REPEATER_ROW)).toEqual(["rp1", 0, "l1"]);
	});

	it("continues a $row path into a grid nested in the row", () => {
		expect(resolveRefPath("$row.sub.a.x", IN_REPEATER_ROW)).toEqual([
			"rp1",
			0,
			"g3",
			"ra",
			"x1",
		]);
	});

	it("needs both an enclosing row and a field name for $row", () => {
		expect(resolveRefPath("$row.hp", ROOT)).toBeUndefined();
		expect(resolveRefPath("$row", IN_REPEATER_ROW)).toBeUndefined();
	});

	it("keys a grid row with no id by its key", () => {
		const nodes = [
			{
				type: "grid",
				name: "g",
				id: "g9",
				items: [{ key: "k", label: "K" }],
				row: [{ type: "input", name: "x", id: "x9" }],
			},
		] as SheetElement[];
		const keys = scopeKeysFor(nodes);
		const scope: Scope = { path: [], keys, root: keys };
		expect(resolveRefPath("g.k.x", scope)).toEqual(["g9", "k", "x9"]);
	});

	it("names a $(inner) segment with the inner ref's value", () => {
		const resolve = (ref: string) => ({ "$row.stat": "dex", pick: "hp" })[ref];
		expect(
			resolveRefPath("stats.$($row.stat).score", IN_REPEATER_ROW, resolve),
		).toEqual(["g1", "r2", "s1"]);
		// A dynamic first segment is a root name, never `$row`.
		expect(resolveRefPath("$(pick)", IN_REPEATER_ROW, resolve)).toEqual(["f1"]);
		expect(
			resolveRefPath("$(pick).level", IN_REPEATER_ROW, () => "$row"),
		).toBeUndefined();
	});

	it("walks a $(inner) segment after $row from the current row", () => {
		expect(resolveRefPath("$row.$(which)", IN_REPEATER_ROW, () => "level")).toEqual([
			"rp1",
			0,
			"l1",
		]);
		expect(resolveRefPath("$row.sub.$(which).x", IN_REPEATER_ROW, () => "a")).toEqual([
			"rp1",
			0,
			"g3",
			"ra",
			"x1",
		]);
		// `hp` is a root field, not one of the row's.
		expect(
			resolveRefPath("$row.$(which)", IN_REPEATER_ROW, () => "hp"),
		).toBeUndefined();
	});

	it("is undefined when a $(inner) value isn't a name", () => {
		for (const value of [undefined, "", 3, "wis"]) {
			expect(
				resolveRefPath("stats.$(pick).score", ROOT, () => value),
				String(value),
			).toBeUndefined();
		}
		// With no resolver, a dynamic segment can't be read.
		expect(resolveRefPath("stats.$(pick).score", ROOT)).toBeUndefined();
	});

	it("is undefined for a malformed $(inner) segment", () => {
		const resolve = () => "dex";
		for (const ref of [
			"stats.$(pick", // unclosed
			"stats.$().score", // empty
			"$(a.$(b))", // nested
			"stats.$(pick)x.score", // not the whole segment
			"stats.x$(pick).score",
		]) {
			expect(resolveRefPath(ref, ROOT, resolve), ref).toBeUndefined();
		}
	});

	it("is undefined for anything that doesn't end on a scalar field", () => {
		for (const ref of [
			"stats", // a whole grid
			"stats.str", // a whole grid row
			"classes", // a whole repeater
			"classes.0.level", // into a repeater
			"hp.x", // past a scalar
			"stats.con.score", // unknown row
			"nope", // unknown field
			"stats..score", // empty segment
			"$index", // store-less
			"$item.label", // store-less
		]) {
			expect(resolveRefPath(ref, ROOT), ref).toBeUndefined();
		}
	});
});
