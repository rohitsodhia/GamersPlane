import createDOMPurify, { type DOMPurify } from "dompurify";
import {
	isYoutubeVideoId,
	youtubeEmbedUrl,
} from "#/components/tiptap/tiptap-node/youtube-node/youtube";

// DOMPurify's own default also admits tel:, ftp:, sms:, and so on; this is the same
// shape (a scheme must be listed, scheme-less values pass) with the list narrowed to
// what the Link extension allows.
const ALLOWED_URI_REGEXP =
	/^(?:(?:https?|mailto):|[^a-z]|[a-z0-9+.-]+(?:[^a-z+.:-]|$))/i;

const YOUTUBE_EMBED_PREFIX = youtubeEmbedUrl("");
const YOUTUBE_IFRAME_ALLOW = "encrypted-media; picture-in-picture; fullscreen";
const LINK_REL = "noopener noreferrer nofollow";

const HEX_COLOR = /^#[0-9a-f]{3,8}$/i;
const FUNCTIONAL_COLOR = /^(?:rgb|hsl)a?\([\d\s.,%/-]+\)$/i;
const NAMED_COLOR = /^[a-z]{3,30}$/i;
const TEXT_ALIGNS: ReadonlySet<string> = new Set([
	"left",
	"right",
	"center",
	"justify",
]);

function isColor(value: string): boolean {
	return (
		HEX_COLOR.test(value) || FUNCTIONAL_COLOR.test(value) || NAMED_COLOR.test(value)
	);
}

// Only the declarations our marks emit (Color, Highlight, TextAlign) survive, and
// only with values of the expected shape.
function cleanStyle(style: string): string {
	const kept: string[] = [];
	for (const declaration of style.split(";")) {
		const colon = declaration.indexOf(":");
		if (colon === -1) continue;
		const property = declaration.slice(0, colon).trim().toLowerCase();
		const value = declaration.slice(colon + 1).trim();
		if (
			((property === "color" || property === "background-color") && isColor(value)) ||
			(property === "text-align" && TEXT_ALIGNS.has(value.toLowerCase()))
		) {
			kept.push(`${property}: ${value}`);
		}
	}
	return kept.join("; ");
}

function isYoutubeEmbedSrc(src: string): boolean {
	return (
		src.startsWith(YOUTUBE_EMBED_PREFIX) &&
		isYoutubeVideoId(src.slice(YOUTUBE_EMBED_PREFIX.length))
	);
}

let purifier: DOMPurify | null = null;

function getPurifier(window: typeof globalThis): DOMPurify {
	if (purifier) return purifier;
	const instance = createDOMPurify(window);

	instance.addHook("uponSanitizeElement", (node, data) => {
		if (data.tagName !== "iframe") return;
		const src = (node as Element).getAttribute("src") ?? "";
		if (!isYoutubeEmbedSrc(src)) node.parentNode?.removeChild(node);
	});

	instance.addHook("uponSanitizeAttribute", (_node, data) => {
		if (data.attrName !== "style") return;
		const cleaned = cleanStyle(data.attrValue);
		if (cleaned === "") data.keepAttr = false;
		else data.attrValue = cleaned;
	});

	instance.addHook("afterSanitizeAttributes", (node) => {
		const element = node as Element;
		const tag = element.tagName;
		if (tag === "IMG" && /^\s*data:/i.test(element.getAttribute("src") ?? "")) {
			element.removeAttribute("src");
		}
		if (tag === "A" && element.hasAttribute("target")) {
			element.setAttribute("rel", LINK_REL);
		}
		if (tag === "IFRAME" && element.getAttribute("allow") !== YOUTUBE_IFRAME_ALLOW) {
			element.removeAttribute("allow");
		}
	});

	purifier = instance;
	return instance;
}

/**
 * Makes the HTML Tiptap generated from a stored document safe to inject. The API
 * doesn't validate document attributes, so this is where hostile values (script
 * URLs, odd styles, foreign iframes) are stopped. Returns an empty string when
 * there is no DOM to sanitize with, never the unsanitized input.
 */
export function sanitizeHtml(html: string): string {
	if (typeof window === "undefined") return "";
	return getPurifier(window).sanitize(html, {
		ADD_TAGS: ["iframe"],
		ADD_ATTR: ["target", "allow", "allowfullscreen"],
		ALLOWED_URI_REGEXP,
	});
}
