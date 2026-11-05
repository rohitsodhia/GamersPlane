// The float choice shared by the box node and images. The document stores the key
// only; the CSS lives in box-node.scss, keyed on `data-float`. "none" is the default
// and renders no attribute at all.
export const FLOATS = [
	{ key: "none", label: "None" },
	{ key: "left", label: "Left" },
	{ key: "right", label: "Right" },
] as const;

export type FloatKey = (typeof FLOATS)[number]["key"];

const FLOAT_KEYS: ReadonlySet<unknown> = new Set(FLOATS.map((f) => f.key));

export function isFloatKey(value: unknown): value is FloatKey {
	return FLOAT_KEYS.has(value);
}

// The `float` attribute spec, for any node that can float. Anything but an
// allowlisted key (including a missing attribute) reads as "none" and renders
// nothing, so a bad value can never reach the page.
export const floatAttribute = {
	default: "none",
	parseHTML: (element: HTMLElement): FloatKey => {
		const value = element.getAttribute("data-float");
		return isFloatKey(value) ? value : "none";
	},
	renderHTML: (attributes: Record<string, unknown>) =>
		isFloatKey(attributes["float"]) && attributes["float"] !== "none"
			? { "data-float": attributes["float"] }
			: {},
};
