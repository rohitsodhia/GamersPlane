import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { validateColumns } from "./style-allowlist";

// `validateColumns` DEV-warns on every dropped entry; silence that so the test
// output only shows real failures. Keep a handle for the cardinality test.
let warnSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
	warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	vi.restoreAllMocks();
});

const ctx = 'grid "x"';

describe("validateColumns — empty / nothing valid", () => {
	it("returns undefined for undefined", () => {
		expect(validateColumns(undefined, ctx)).toBeUndefined();
	});

	it("returns undefined for an empty array", () => {
		expect(validateColumns([], ctx)).toBeUndefined();
	});

	it("returns undefined when every entry is rejected", () => {
		expect(validateColumns(["calc(100% - 1rem)", "bogus"], ctx)).toBeUndefined();
	});
});

describe("validateColumns — accepted track tokens", () => {
	it("keeps lengths, percentages and 0", () => {
		expect(validateColumns(["10rem", "120px", "50%", "0"], ctx)).toBe(
			"10rem 120px 50% 0",
		);
	});

	it("keeps fr units", () => {
		expect(validateColumns(["1fr", "2.5fr"], ctx)).toBe("1fr 2.5fr");
	});

	it("keeps the sizing keywords", () => {
		expect(validateColumns(["auto", "min-content", "max-content"], ctx)).toBe(
			"auto min-content max-content",
		);
	});

	it("keeps a --char-sheet-* custom property", () => {
		expect(validateColumns(["var(--char-sheet-label-col)", "1fr"], ctx)).toBe(
			"var(--char-sheet-label-col) 1fr",
		);
	});

	it("keeps minmax() of two size tokens", () => {
		expect(validateColumns(["minmax(4rem, 6rem)", "minmax(0, 1fr)"], ctx)).toBe(
			"minmax(4rem, 6rem) minmax(0, 1fr)",
		);
	});

	it("keeps repeat() with an integer count", () => {
		expect(validateColumns(["repeat(3, max-content)"], ctx)).toBe(
			"repeat(3, max-content)",
		);
	});

	it("keeps repeat() with auto-fill / auto-fit and a nested minmax", () => {
		expect(validateColumns(["1fr", "repeat(auto-fill, minmax(8rem, 1fr))"], ctx)).toBe(
			"1fr repeat(auto-fill, minmax(8rem, 1fr))",
		);
		expect(validateColumns(["repeat(auto-fit, 10rem)"], ctx)).toBe(
			"repeat(auto-fit, 10rem)",
		);
	});

	it("keeps a multi-track repeat() body and two-digit / upper-bound counts", () => {
		expect(validateColumns(["repeat(3, 1fr max-content)"], ctx)).toBe(
			"repeat(3, 1fr max-content)",
		);
		expect(validateColumns(["repeat(12, 10rem)"], ctx)).toBe("repeat(12, 10rem)");
		expect(validateColumns(["repeat(50, 1fr)"], ctx)).toBe("repeat(50, 1fr)");
	});

	it("trims surrounding whitespace on a kept entry", () => {
		expect(validateColumns(["  1fr  ", "max-content"], ctx)).toBe("1fr max-content");
	});
});

describe("validateColumns — rejected entries are dropped, the rest kept", () => {
	it("drops calc()", () => {
		expect(validateColumns(["calc(100% - 3rem)", "1fr"], ctx)).toBe("1fr");
	});

	it("drops a foreign custom property", () => {
		expect(validateColumns(["var(--evil)", "1fr"], ctx)).toBe("1fr");
	});

	it("drops a negative length", () => {
		expect(validateColumns(["-3rem", "1fr"], ctx)).toBe("1fr");
	});

	it("drops a malformed fraction", () => {
		expect(validateColumns(["-1fr", "1fr"], ctx)).toBe("1fr");
		expect(validateColumns([".5fr", "1fr"], ctx)).toBe("1fr");
		expect(validateColumns(["fr", "1fr"], ctx)).toBe("1fr");
	});

	it("drops an entry that packs several tokens into one string", () => {
		expect(validateColumns(["1fr 2fr", "max-content"], ctx)).toBe("max-content");
	});

	it("drops an unbalanced or empty entry", () => {
		expect(validateColumns(["repeat(3, 1fr", "1fr"], ctx)).toBe("1fr");
		expect(validateColumns(["", "1fr"], ctx)).toBe("1fr");
	});

	it("drops repeat() with an out-of-range count", () => {
		expect(validateColumns(["repeat(51, 1fr)", "1fr"], ctx)).toBe("1fr");
		expect(validateColumns(["repeat(0, 1fr)", "1fr"], ctx)).toBe("1fr");
	});

	it("drops nested repeat()", () => {
		expect(validateColumns(["repeat(2, repeat(2, 1fr))", "1fr"], ctx)).toBe("1fr");
	});

	it("drops minmax() with the wrong number of arguments", () => {
		expect(validateColumns(["minmax(1fr)", "1fr"], ctx)).toBe("1fr");
		expect(validateColumns(["minmax(1rem, 2rem, 3rem)", "1fr"], ctx)).toBe("1fr");
	});

	it("warns once per dropped entry", () => {
		validateColumns(["calc(1px)", "bogus", "1fr"], ctx);
		expect(warnSpy).toHaveBeenCalledTimes(2);
	});
});
