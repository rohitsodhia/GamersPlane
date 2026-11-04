import { mergeAttributes } from "@tiptap/core";
import { OrderedList } from "@tiptap/extension-list";

// HTML's `<ol type>` values: decimal, then lower and upper alpha and roman.
export const ORDERED_LIST_TYPES = [
	{ key: "1", label: "1, 2, 3" },
	{ key: "a", label: "a, b, c" },
	{ key: "A", label: "A, B, C" },
	{ key: "i", label: "i, ii, iii" },
	{ key: "I", label: "I, II, III" },
] as const;

export type OrderedListType = (typeof ORDERED_LIST_TYPES)[number]["key"];

const TYPE_KEYS: ReadonlySet<unknown> = new Set(ORDERED_LIST_TYPES.map((t) => t.key));

export function safeListType(value: unknown): OrderedListType | null {
	return TYPE_KEYS.has(value) ? (value as OrderedListType) : null;
}

export function safeListStart(value: unknown): number {
	return typeof value === "number" && Number.isSafeInteger(value) && value >= 1
		? value
		: 1;
}

// The stock list keeps whatever `start` and `type` it is handed (a NaN start, any
// string as a type). This narrows both to a positive integer and the five type
// keys, whether they come from pasted HTML or from a stored document.
export const SafeOrderedList = OrderedList.extend({
	addAttributes() {
		return {
			start: {
				default: 1,
				parseHTML: (element) =>
					safeListStart(Number.parseInt(element.getAttribute("start") ?? "", 10)),
			},
			type: {
				default: null,
				parseHTML: (element) => safeListType(element.getAttribute("type")),
			},
		};
	},

	renderHTML({ HTMLAttributes }) {
		const { start, type, ...rest } = HTMLAttributes;
		const attrs = mergeAttributes(this.options.HTMLAttributes, rest);
		const safeStart = safeListStart(start);
		if (safeStart !== 1) attrs["start"] = safeStart;
		const safeType = safeListType(type);
		if (safeType && safeType !== "1") attrs["type"] = safeType;
		return ["ol", attrs, 0];
	},
});
