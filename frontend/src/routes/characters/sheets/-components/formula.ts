// Pure evaluator for character-sheet computed-field formulas.
//
// A formula is a small expression TREE (AST) authored directly as JSON — there
// is no string syntax yet. A later pass may add a readable string DSL, but it
// will parse down to exactly these nodes, so this evaluator is the stable half
// and can be built now.
//
//   Expr :=
//     | number                        literal, e.g. 10
//     | boolean                       literal
//     | { ref: string }               read another field's value (the caller
//                                     resolves the name against the value store)
//     | { op: OpName, args: Expr[] }   apply a whitelisted operator / function
//
// `op` is a FIXED whitelist: no property access, no function lookup by string,
// no `eval`. Same threat model as the "no author-supplied CSS" decision — the
// sheet JSON is untrusted.
//
// A `ref` whose name starts with `$` is "magic": it is resolved from render
// context rather than the value store (see `createRefResolver` in
// `loop-context.tsx`). `$index` is the 0-based iteration index of the nearest
// enclosing `loop`. The evaluator does not special-case these — resolution is
// entirely the caller's resolver's job — but `isMagicRef` and the `collectRefs`
// skip below keep the (future) dependency graph from treating them as store
// fields.
//
// Not here (deferred, by design): the dependency graph / topological recompute
// order / cycle detection that a full spreadsheet-style engine needs. This
// function just evaluates one expression given a way to resolve refs. Chained
// `computed`s and cycle detection are the graph layer's job.

export type Expr = number | boolean | RefExpr | OpExpr;

export interface RefExpr {
	/** A field name, resolved by the caller against the current value scope. */
	ref: string;
}

export interface OpExpr {
	op: OpName;
	args: Expr[];
}

/**
 * Every operator / function the evaluator understands. Kept as a const array so
 * it doubles as the validation whitelist (`isOpName`).
 */
export const OP_NAMES = [
	// arithmetic (binary)
	"+",
	"-",
	"*",
	"/",
	"%",
	// arithmetic (unary)
	"neg",
	// comparison (binary) -> boolean
	"==",
	"!=",
	"<",
	"<=",
	">",
	">=",
	// logical -> boolean
	"&&",
	"||",
	"!",
	// conditional: if(cond, then, else)
	"if",
	// numeric functions
	"floor",
	"ceil",
	"round",
	"abs",
	"min",
	"max",
	"clamp",
	"sum",
] as const;

export type OpName = (typeof OP_NAMES)[number];

const OP_NAME_SET: ReadonlySet<string> = new Set(OP_NAMES);

/** Is `op` a whitelisted operator name? For the (future) validation layer. */
export function isOpName(op: string): op is OpName {
	return OP_NAME_SET.has(op);
}

/**
 * A `$`-prefixed ref resolved from render context (loop position, current item),
 * not the value store. See the header comment and `createRefResolver`.
 */
export function isMagicRef(name: string): boolean {
	return name.startsWith("$");
}

/**
 * Resolves a bare `ref` name to its stored value. Supplied by the caller: the
 * `computed` element wires this to a lexical walk over the sheet value store
 * (row scope, then outward, then sheet). The evaluator never sees the store.
 */
export type RefResolver = (name: string) => unknown;

/** A fully evaluated formula value. */
export type FormulaValue = number | boolean;

export class FormulaError extends Error {
	override name = "FormulaError";
}

/**
 * Evaluate `expr`, resolving `{ ref }` nodes through `resolve`.
 *
 * Coercion is deliberately lenient (this drives a character sheet, not a
 * compiler): a ref that is missing, empty, or non-numeric resolves to `0`;
 * booleans act as `0` / `1` in arithmetic and as themselves in conditionals;
 * division / modulo by zero yields `0`.
 *
 * Throws `FormulaError` only for a malformed tree: an unknown `op`, a node that
 * is neither literal / ref / op, or an op given the wrong number of args.
 */
export function evaluate(expr: Expr, resolve: RefResolver): FormulaValue {
	if (typeof expr === "number" || typeof expr === "boolean") return expr;

	if (expr !== null && typeof expr === "object" && "ref" in expr) {
		return toNumber(resolve(expr.ref));
	}

	if (
		expr === null ||
		typeof expr !== "object" ||
		!("op" in expr) ||
		!Array.isArray(expr.args)
	) {
		throw new FormulaError(`not a formula node: ${JSON.stringify(expr)}`);
	}

	const { op, args } = expr;
	const ev = (e: Expr) => evaluate(e, resolve);

	// Short-circuiting / branching ops evaluate their args lazily.
	switch (op) {
		case "&&":
			expectArity(args, 2, op);
			return truthy(ev(args[0])) ? truthy(ev(args[1])) : false;
		case "||":
			expectArity(args, 2, op);
			return truthy(ev(args[0])) ? true : truthy(ev(args[1]));
		case "!":
			expectArity(args, 1, op);
			return !truthy(ev(args[0]));
		case "if":
			expectArity(args, 3, op);
			return truthy(ev(args[0])) ? ev(args[1]) : ev(args[2]);
		case "neg":
			expectArity(args, 1, op);
			return -num(ev(args[0]));
	}

	if (op in NUMERIC_BINARY) {
		expectArity(args, 2, op);
		return NUMERIC_BINARY[op](num(ev(args[0])), num(ev(args[1])));
	}
	if (op in COMPARISON) {
		expectArity(args, 2, op);
		return COMPARISON[op](num(ev(args[0])), num(ev(args[1])));
	}

	const vals = args.map((a) => num(ev(a)));
	switch (op) {
		case "floor":
			expectArity(args, 1, op);
			return Math.floor(vals[0]);
		case "ceil":
			expectArity(args, 1, op);
			return Math.ceil(vals[0]);
		case "round":
			expectArity(args, 1, op);
			return Math.round(vals[0]);
		case "abs":
			expectArity(args, 1, op);
			return Math.abs(vals[0]);
		case "min":
			expectMinArity(args, 1, op);
			return Math.min(...vals);
		case "max":
			expectMinArity(args, 1, op);
			return Math.max(...vals);
		case "sum":
			return vals.reduce((a, b) => a + b, 0);
		case "clamp": {
			expectArity(args, 3, op);
			const [v, lo, hi] = vals;
			return Math.min(Math.max(v, lo), hi);
		}
		default:
			throw new FormulaError(`unknown formula op: ${JSON.stringify(op)}`);
	}
}

/**
 * Every distinct `ref` name in a formula, in first-encounter order. The
 * `computed` element subscribes to each so it recomputes when a dependency
 * changes; the validation layer uses it to build the dependency graph.
 */
export function collectRefs(expr: Expr): string[] {
	const out: string[] = [];
	const seen = new Set<string>();
	const walk = (e: Expr) => {
		if (typeof e === "number" || typeof e === "boolean" || e === null) return;
		if ("ref" in e) {
			// Magic refs (`$index`, …) come from render context, not the store, so
			// they are not dependencies the graph layer needs to track.
			if (isMagicRef(e.ref)) return;
			if (!seen.has(e.ref)) {
				seen.add(e.ref);
				out.push(e.ref);
			}
			return;
		}
		if ("op" in e && Array.isArray(e.args)) for (const a of e.args) walk(a);
	};
	walk(expr);
	return out;
}

// --- operator tables -------------------------------------------------------

const NUMERIC_BINARY: Record<string, (a: number, b: number) => number> = {
	"+": (a, b) => a + b,
	"-": (a, b) => a - b,
	"*": (a, b) => a * b,
	"/": (a, b) => (b === 0 ? 0 : a / b),
	"%": (a, b) => (b === 0 ? 0 : a % b),
};

const COMPARISON: Record<string, (a: number, b: number) => boolean> = {
	"==": (a, b) => a === b,
	"!=": (a, b) => a !== b,
	"<": (a, b) => a < b,
	"<=": (a, b) => a <= b,
	">": (a, b) => a > b,
	">=": (a, b) => a >= b,
};

// --- coercion & arity helpers ----------------------------------------------

/** Store value (unknown, usually a string from an <input>) -> number. */
function toNumber(raw: unknown): number {
	if (raw === null || raw === undefined || raw === "") return 0;
	if (typeof raw === "boolean") return raw ? 1 : 0;
	const n = Number(raw);
	return Number.isNaN(n) ? 0 : n;
}

/** Evaluated value -> number, for use in an arithmetic context. */
function num(v: FormulaValue): number {
	return typeof v === "boolean" ? (v ? 1 : 0) : v;
}

/** Evaluated value -> boolean, for use in a conditional / logical context. */
function truthy(v: FormulaValue): boolean {
	return typeof v === "boolean" ? v : v !== 0 && !Number.isNaN(v);
}

function expectArity(args: Expr[], n: number, op: string): void {
	if (args.length !== n) {
		throw new FormulaError(
			`formula op "${op}" expects ${n} argument(s), got ${args.length}`,
		);
	}
}

function expectMinArity(args: Expr[], n: number, op: string): void {
	if (args.length < n) {
		throw new FormulaError(
			`formula op "${op}" expects at least ${n} argument(s), got ${args.length}`,
		);
	}
}
