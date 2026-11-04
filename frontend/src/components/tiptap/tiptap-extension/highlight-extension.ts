import { Highlight } from "@tiptap/extension-highlight";

const HEX_COLOR = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i;
const NAMED_COLOR = /^[a-z]{3,20}$/i;

// A highlight color goes straight into an inline `style`, so only a plain hex or a
// color name is accepted; anything else (a `;`, a `url(`, ...) is dropped and the
// text is left unhighlighted.
export function safeHighlightColor(value: unknown): string | null {
	if (typeof value !== "string") return null;
	const color = value.trim();
	return HEX_COLOR.test(color) || NAMED_COLOR.test(color) ? color : null;
}

// Highlight leaves the text color alone (`color: inherit`), which in dark mode is
// near-white text on whatever the highlight is. For hex colors pick black or white
// by luminance instead; named colors are only used for a couple of palette entries
// and fall back to inheriting.
export function highlightTextColor(color: string): string {
	if (!HEX_COLOR.test(color)) return "inherit";
	const hex =
		color.length === 4
			? [...color.slice(1)].map((c) => c + c).join("")
			: color.slice(1);
	const [r, g, b] = [0, 2, 4].map((i) => {
		const channel = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
		return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
	}) as [number, number, number];
	const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
	return luminance > 0.179 ? "#000000" : "#ffffff";
}

// Replaces the stock multicolor attribute so the color is validated and the text
// color is set for contrast; it reads `data-color` only, never an inline style.
export const SafeHighlight = Highlight.configure({
	multicolor: true,
}).extend({
	// Wraps the text color's span instead of sitting inside it. The highlight sets a
	// contrast color of its own (below), and when it is the inner element that
	// overrides a text color the user picked, so color and highlight couldn't be
	// combined. Outermost, its color is only the default and the span's color wins.
	priority: 1000,

	addAttributes() {
		return {
			color: {
				default: null,
				parseHTML: (element) => safeHighlightColor(element.getAttribute("data-color")),
				renderHTML: (attributes) => {
					const color = safeHighlightColor(attributes["color"]);
					if (!color) return {};
					return {
						"data-color": color,
						style: `background-color: ${color}; color: ${highlightTextColor(color)}`,
					};
				},
			},
		};
	},
});
