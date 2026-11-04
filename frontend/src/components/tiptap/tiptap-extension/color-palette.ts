export type PaletteColor = { name: string; value: string };

// Two 14-color palettes (the swatch grid is 7 wide, so two full rows), each spread
// across the hue wheel with no near-duplicates, as the hex values the color and
// highlight marks store. v1's `[color=blue]` and friends were bare CSS names, many
// of them close together (red, maroon, darkred, brown, saddlebrown); old posts keep
// whatever color they have, and anything else is still reachable from the picker.

// Text colors: mid-tones that stay readable on the light and dark page. The greys
// come first as a lightness ramp, then the hues in wheel order.
export const TEXT_PALETTE: readonly PaletteColor[] = [
	{ name: "Black", value: "#000000" },
	{ name: "Dark grey", value: "#555555" },
	{ name: "Grey", value: "#999999" },
	{ name: "White", value: "#ffffff" },
	{ name: "Red", value: "#d62828" },
	{ name: "Orange", value: "#f77f00" },
	{ name: "Gold", value: "#d4a017" },
	{ name: "Green", value: "#2e9e3e" },
	{ name: "Teal", value: "#008080" },
	{ name: "Sky blue", value: "#1ea5d8" },
	{ name: "Blue", value: "#1f4fd8" },
	{ name: "Purple", value: "#7b2cbf" },
	{ name: "Pink", value: "#e0558f" },
	{ name: "Brown", value: "#7a4a21" },
];

// Highlight colors: brighter fills, since the text on them is switched to black or
// white by contrast (see highlight-extension.ts). Hues in wheel order, then the
// neutrals.
export const HIGHLIGHT_PALETTE: readonly PaletteColor[] = [
	{ name: "Yellow", value: "#ffeb3b" },
	{ name: "Lime", value: "#d4e157" },
	{ name: "Green", value: "#81c784" },
	{ name: "Cyan", value: "#4dd0e1" },
	{ name: "Blue", value: "#64b5f6" },
	{ name: "Purple", value: "#ba68c8" },
	{ name: "Pink", value: "#f48fb1" },
	{ name: "Red", value: "#ef5350" },
	{ name: "Orange", value: "#ff9800" },
	{ name: "Brown", value: "#a1887f" },
	{ name: "Silver", value: "#c0c0c0" },
	{ name: "Dark grey", value: "#555555" },
	{ name: "Black", value: "#000000" },
	{ name: "White", value: "#ffffff" },
];
