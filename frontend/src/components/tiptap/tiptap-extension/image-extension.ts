import { mergeAttributes } from "@tiptap/core";
import { Image } from "@tiptap/extension-image";
import { Plugin } from "@tiptap/pm/state";
import {
	floatAttribute,
	isFloatKey,
} from "#/components/tiptap/tiptap-extension/float-attribute";

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		imageFloat: {
			/** Float the selected image left or right, or back to none. */
			setImageFloat: (float: "none" | "left" | "right") => ReturnType;
		};
		imageLink: {
			/**
			 * Make the selected image a link to a bigger image or a page. Returns false
			 * (and changes nothing) when the address isn't a plain http(s) URL.
			 */
			setImageLink: (href: string) => ReturnType;
			/** Take the link off the selected image. */
			unsetImageLink: () => ReturnType;
		};
	}
}

const MAX_IMAGE_LINK_LENGTH = 2048;
const IMAGE_LINK_CLASS = "image-link";

/**
 * The normalized address when `value` is an absolute http or https URL, else null.
 * Everything else is refused: `javascript:`, `data:`, `mailto:`, protocol-relative
 * (`//host`) and relative addresses, and addresses carrying credentials.
 */
export function safeImageLink(value: unknown): string | null {
	if (typeof value !== "string") return null;
	const text = value.trim();
	if (!text || text.length > MAX_IMAGE_LINK_LENGTH) return null;
	let url: URL;
	try {
		url = new URL(text);
	} catch {
		return null;
	}
	if (url.protocol !== "http:" && url.protocol !== "https:") return null;
	if (url.username || url.password) return null;
	return url.href;
}

// Pasted `<a href><img></a>` markup (no data attribute yet) reads its address from
// the wrapping anchor.
function hrefFromElement(element: HTMLElement): string | null {
	const stored = safeImageLink(element.getAttribute("data-href"));
	if (stored) return stored;
	const parent = element.parentElement;
	return parent?.tagName === "A" ? safeImageLink(parent.getAttribute("href")) : null;
}

// The stock image plus a `float` attribute (key only, see float-attribute.ts) and an
// optional `href`. A linked image renders as `<a><img></a>`; the address is also
// kept on the img as `data-href`, which is what parsing reads back first. Only
// validated http(s) addresses are ever rendered, and nothing is read from styles.
export const FloatImage = Image.extend({
	addAttributes() {
		return {
			...this.parent?.(),
			float: floatAttribute,
			href: {
				default: null,
				parseHTML: hrefFromElement,
				renderHTML: (attributes: Record<string, unknown>) => {
					const href = safeImageLink(attributes["href"]);
					return href ? { "data-href": href } : {};
				},
			},
		};
	},

	renderHTML({ node, HTMLAttributes }) {
		const image = ["img", mergeAttributes(this.options.HTMLAttributes, HTMLAttributes)];
		const href = safeImageLink(node.attrs["href"]);
		if (!href) return image as ["img", Record<string, string>];
		return [
			"a",
			{
				href,
				rel: "noopener noreferrer nofollow",
				target: "_blank",
				class: IMAGE_LINK_CLASS,
			},
			image,
		];
	},

	addCommands() {
		return {
			...this.parent?.(),
			setImageFloat:
				(float) =>
				({ commands }) =>
					isFloatKey(float) && commands.updateAttributes(this.name, { float }),
			setImageLink:
				(href) =>
				({ commands }) => {
					const safe = safeImageLink(href);
					return safe !== null && commands.updateAttributes(this.name, { href: safe });
				},
			unsetImageLink:
				() =>
				({ commands }) =>
					commands.updateAttributes(this.name, { href: null }),
		};
	},

	addProseMirrorPlugins() {
		return [
			...(this.parent?.() ?? []),
			new Plugin({
				props: {
					// Clicking a linked image in the editor selects it; it must not open the
					// link. Returning false leaves the usual selection handling to run.
					handleClick: (view, _pos, event) => {
						const target = event.target;
						if (
							view.editable &&
							target instanceof Element &&
							target.closest(`a.${IMAGE_LINK_CLASS}`)
						) {
							event.preventDefault();
						}
						return false;
					},
				},
			}),
		];
	},
});
