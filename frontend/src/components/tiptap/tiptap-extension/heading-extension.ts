import { mergeAttributes } from "@tiptap/core";
import { Heading } from "@tiptap/extension-heading";

// Headings reuse the site's banner classes instead of restyling h1/h2 in the
// content CSS: h1 is the orange `headerbar`, h2 the dark one (`hb-dark`). h3 and h4
// stay plain, styled in heading-node.scss.
const BANNER_CLASSES: Partial<Record<number, string>> = {
	1: "headerbar",
	2: "headerbar hb-dark",
};

export const BannerHeading = Heading.extend({
	renderHTML({ node, HTMLAttributes }) {
		const level: number = this.options.levels.includes(node.attrs["level"])
			? node.attrs["level"]
			: this.options.levels[0];
		const className = BANNER_CLASSES[level];
		return [
			`h${level}`,
			mergeAttributes(
				this.options.HTMLAttributes,
				HTMLAttributes,
				className ? { class: className } : {},
			),
			0,
		];
	},
});
