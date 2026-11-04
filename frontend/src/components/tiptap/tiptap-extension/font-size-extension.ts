import { Mark } from "@tiptap/core";

// The five v1 `[f=]` size words. The document stores the key only; the real size
// lives in text-format.scss, keyed on `data-font-size`. "Normal" is no mark.
export const FONT_SIZES = [
	{ key: "tiny", label: "Tiny" },
	{ key: "small", label: "Small" },
	{ key: "large", label: "Large" },
	{ key: "huge", label: "Huge" },
	{ key: "gargantuan", label: "Gargantuan" },
] as const;

export type FontSizeKey = (typeof FONT_SIZES)[number]["key"];

const FONT_SIZE_KEYS: ReadonlySet<unknown> = new Set(FONT_SIZES.map((s) => s.key));

export function isFontSizeKey(value: unknown): value is FontSizeKey {
	return FONT_SIZE_KEYS.has(value);
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		// Named apart from text-style's own (unregistered) `fontSize` commands, whose
		// types would otherwise clash with these.
		fontSizePreset: {
			setFontSizePreset: (size: FontSizeKey) => ReturnType;
			unsetFontSizePreset: () => ReturnType;
		};
	}
}

// Deliberately its own mark rather than an attribute on TextStyle: TextStyle only
// parses spans that carry an inline `style`, so a `data-` only span would not
// round-trip, and keeping the attribute off TextStyle means pasted inline
// `font-size` styles can never reach this mark. Parsing reads `data-font-size`
// alone, and only an allowlisted key.
export const FontSize = Mark.create({
	name: "fontSize",

	// Left inclusive (the default) like bold and italic: picking a size at an empty
	// cursor has to carry on past the first typed character, and a non-inclusive
	// mark applies to that one character only.

	addAttributes() {
		return {
			size: {
				default: null,
				parseHTML: (element) => {
					const size = element.getAttribute("data-font-size");
					return isFontSizeKey(size) ? size : null;
				},
				renderHTML: (attributes) =>
					isFontSizeKey(attributes["size"])
						? { "data-font-size": attributes["size"] }
						: {},
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: "span[data-font-size]",
				getAttrs: (element) =>
					isFontSizeKey((element as HTMLElement).getAttribute("data-font-size"))
						? {}
						: false,
			},
		];
	},

	renderHTML({ HTMLAttributes }) {
		return ["span", HTMLAttributes, 0];
	},

	addCommands() {
		return {
			setFontSizePreset:
				(size) =>
				({ commands }) =>
					isFontSizeKey(size) && commands.setMark(this.name, { size }),
			unsetFontSizePreset:
				() =>
				({ commands }) =>
					commands.unsetMark(this.name),
		};
	},
});
