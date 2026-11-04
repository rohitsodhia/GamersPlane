import { Mark } from "@tiptap/core";

// The v1 `[f=]` font words. The document stores the key only; the real font stacks
// live in text-format.scss, keyed on `data-font` (keep the two lists in step).
export const FONT_FAMILIES = [
	{ key: "agency", label: "Agency FB" },
	{ key: "aladin", label: "Aladin" },
	{ key: "aniron", label: "Aniron" },
	{ key: "blackops", label: "Black Ops One" },
	{ key: "cabin", label: "Cabin Sketch" },
	{ key: "cursive", label: "Cursive" },
	{ key: "dumbledor", label: "Dumbledor" },
	{ key: "eagle", label: "Eagle Lake" },
	{ key: "elite", label: "Special Elite" },
	{ key: "fell", label: "IM Fell English" },
	{ key: "goudy", label: "Goudy Bookletter 1911" },
	{ key: "gugi", label: "Gugi" },
	{ key: "iceland", label: "Iceland" },
	{ key: "kelt", label: "Kelt" },
	{ key: "neuropol", label: "Neuropol" },
	{ key: "nightshade", label: "Jim Nightshade" },
	{ key: "opensans", label: "Open Sans" },
	{ key: "ostrich", label: "Ostrich Sans" },
	{ key: "quint", label: "Quintessential" },
	{ key: "stalinist", label: "Stalinist One" },
	{ key: "start", label: "Press Start 2P" },
] as const;

export type FontFamilyKey = (typeof FONT_FAMILIES)[number]["key"];

const FONT_FAMILY_KEYS: ReadonlySet<unknown> = new Set(FONT_FAMILIES.map((f) => f.key));

export function isFontFamilyKey(value: unknown): value is FontFamilyKey {
	return FONT_FAMILY_KEYS.has(value);
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		// Named apart from text-style's own (unregistered) `fontFamily` commands,
		// whose types would otherwise clash with these.
		fontFamilyPreset: {
			setFontFamilyPreset: (font: FontFamilyKey) => ReturnType;
			unsetFontFamilyPreset: () => ReturnType;
		};
	}
}

// Its own mark for the same reasons as FontSize: parsing reads `data-font` alone
// and only an allowlisted key, so a pasted inline `font-family` is never used.
export const FontFamily = Mark.create({
	name: "fontFamily",

	// Left inclusive (the default) like bold and italic: picking a font at an empty
	// cursor has to carry on past the first typed character, and a non-inclusive
	// mark applies to that one character only.

	addAttributes() {
		return {
			font: {
				default: null,
				parseHTML: (element) => {
					const font = element.getAttribute("data-font");
					return isFontFamilyKey(font) ? font : null;
				},
				renderHTML: (attributes) =>
					isFontFamilyKey(attributes["font"])
						? { "data-font": attributes["font"] }
						: {},
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: "span[data-font]",
				getAttrs: (element) =>
					isFontFamilyKey((element as HTMLElement).getAttribute("data-font"))
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
			setFontFamilyPreset:
				(font) =>
				({ commands }) =>
					isFontFamilyKey(font) && commands.setMark(this.name, { font }),
			unsetFontFamilyPreset:
				() =>
				({ commands }) =>
					commands.unsetMark(this.name),
		};
	},
});
