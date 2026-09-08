import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { filterUtilityClasses, isAllowedUtilityClass } from "./style-allowlist";

// `filterUtilityClasses` DEV-warns on every dropped token; silence it so the
// test output only shows real failures. Keep a handle for the cardinality test.
let warnSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
	warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	vi.restoreAllMocks();
});

const ctx = 'input "score"';

describe("isAllowedUtilityClass", () => {
	it("accepts a char-sheet-* token, including a BEM double-hyphen suffix", () => {
		expect(isAllowedUtilityClass("char-sheet-field")).toBe(true);
		expect(isAllowedUtilityClass("char-sheet-group--inline")).toBe(true);
	});

	it("accepts headerbar, the one non-prefixed exception", () => {
		expect(isAllowedUtilityClass("headerbar")).toBe(true);
	});

	it("rejects headerbar with anything appended", () => {
		expect(isAllowedUtilityClass("headerbars")).toBe(false);
	});

	it("rejects uppercase in the suffix (policy: [a-z], not [a-zA-Z])", () => {
		expect(isAllowedUtilityClass("char-sheet-Foo")).toBe(false);
	});

	it("rejects an unrelated app / global class", () => {
		expect(isAllowedUtilityClass("headerbar-wrap")).toBe(false);
		expect(isAllowedUtilityClass("btn-primary")).toBe(false);
	});

	it("rejects a token that only embeds the prefix mid-string", () => {
		expect(isAllowedUtilityClass("x-char-sheet-field")).toBe(false);
	});
});

describe("filterUtilityClasses", () => {
	it("returns an empty array for an empty iterable", () => {
		expect(filterUtilityClasses([], ctx)).toEqual([]);
	});

	it("keeps allowed tokens in order and drops the rest", () => {
		expect(
			filterUtilityClasses(["char-sheet-field", "btn-primary", "headerbar"], ctx),
		).toEqual(["char-sheet-field", "headerbar"]);
	});

	it("splits a whitespace-joined entry and checks each token (class_when key)", () => {
		expect(
			filterUtilityClasses(["char-sheet-value--multiline evil-class"], ctx),
		).toEqual(["char-sheet-value--multiline"]);
	});

	it("passes duplicate tokens through unchanged (callers join into className)", () => {
		expect(filterUtilityClasses(["char-sheet-a char-sheet-a"], ctx)).toEqual([
			"char-sheet-a",
			"char-sheet-a",
		]);
	});

	it("ignores empty / whitespace-only entries without warning", () => {
		expect(filterUtilityClasses(["", "   "], ctx)).toEqual([]);
		expect(warnSpy).not.toHaveBeenCalled();
	});

	it("warns once per dropped token occurrence", () => {
		filterUtilityClasses(["bad-one bad-two", "char-sheet-ok"], ctx);
		expect(warnSpy).toHaveBeenCalledTimes(2);
	});
});
