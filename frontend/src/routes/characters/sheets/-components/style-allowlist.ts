// Validates and resolves an element's `styles` bag (see `types.ts`'s
// `StyleProp`) into real inline CSS. A sheet is user-authored content, so —
// like `class` — this is a genuine allowlist: both the property and its value
// syntax are checked. Anything not covered here is dropped (DEV-warned), never
// forwarded to the DOM.

import type { CSSProperties } from "react";
import type { StyleBundle, StyleProp } from "./types";

const NUMBER = String.raw`-?\d+(\.\d+)?`;
const LENGTH_RE = new RegExp(`^(${NUMBER}(px|rem|em|%|ch|vh|vw|ex)|0)$`);
const LENGTH_OR_AUTO_RE = new RegExp(`^(${NUMBER}(px|rem|em|%|ch|vh|vw|ex)|0|auto)$`);
const isLength = (v: string) => LENGTH_RE.test(v);
const isLengthOrAuto = (v: string) => LENGTH_OR_AUTO_RE.test(v);

const HEX_COLOR_RE = /^#[0-9a-fA-F]{3,8}$/;
const RGB_COLOR_RE =
	/^rgba?\(\s*\d{1,3}%?\s*,\s*\d{1,3}%?\s*,\s*\d{1,3}%?\s*(,\s*(0|1|0?\.\d+)\s*)?\)$/;
const HSL_COLOR_RE =
	/^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%\s*(,\s*(0|1|0?\.\d+)\s*)?\)$/;
// Named colors ("red", "transparent", "currentColor", ...): a bare CSS ident.
// Not checked against the real color-name table — a made-up name just fails
// silently in the browser, same as any other invalid CSS value.
const NAMED_COLOR_RE = /^[a-zA-Z]+$/;
const isColor = (v: string) =>
	HEX_COLOR_RE.test(v) ||
	RGB_COLOR_RE.test(v) ||
	HSL_COLOR_RE.test(v) ||
	NAMED_COLOR_RE.test(v);

const isEnum =
	<T extends string>(values: readonly T[]) =>
	(v: string): v is T =>
		(values as readonly string[]).includes(v);

/** Up to `maxTokens` whitespace-separated values (e.g. `"4px 8px"`), each valid per `tokenOk`. */
const isSpaceSeparated =
	(tokenOk: (t: string) => boolean, maxTokens: number) => (v: string) => {
		const tokens = v.trim().split(/\s+/);
		return tokens.length > 0 && tokens.length <= maxTokens && tokens.every(tokenOk);
	};

const BG_SIZE_KEYWORDS = ["cover", "contain", "auto"];
const BG_POSITION_KEYWORDS = ["left", "right", "center", "top", "bottom"];
const isBackgroundSize = isSpaceSeparated(
	(t) => BG_SIZE_KEYWORDS.includes(t) || isLength(t),
	2,
);
const isBackgroundPosition = isSpaceSeparated(
	(t) => BG_POSITION_KEYWORDS.includes(t) || isLength(t),
	2,
);

// `background-image` is the one property that reaches out to a URL, so beyond
// syntax it's scheme-checked: only https and same-site-relative paths, never
// `data:`/`javascript:`/anything else — a sheet shouldn't be able to turn into
// a tracking pixel (or worse) via an author-supplied image.
const BG_IMAGE_RE = /^url\((['"]?)(https:\/\/[^'")]+|\/[^'")]+)\1\)$/;
const isBackgroundImage = (v: string) => BG_IMAGE_RE.test(v.trim());

interface StyleRule {
	/** The real CSS property this maps to, camelCase (as React's `style` expects). */
	cssProperty: string;
	valid: (value: string) => boolean;
}

const STYLE_RULES: Record<StyleProp, StyleRule> = {
	position: { cssProperty: "position", valid: isEnum(["absolute", "relative"]) },
	left: { cssProperty: "left", valid: isLength },
	right: { cssProperty: "right", valid: isLength },
	top: { cssProperty: "top", valid: isLength },
	bottom: { cssProperty: "bottom", valid: isLength },
	width: { cssProperty: "width", valid: isLengthOrAuto },
	height: { cssProperty: "height", valid: isLengthOrAuto },
	padding: { cssProperty: "padding", valid: isSpaceSeparated(isLength, 4) },
	margin: {
		cssProperty: "margin",
		valid: isSpaceSeparated((t) => t === "auto" || isLength(t), 4),
	},
	"background-color": { cssProperty: "backgroundColor", valid: isColor },
	"background-image": { cssProperty: "backgroundImage", valid: isBackgroundImage },
	"background-size": { cssProperty: "backgroundSize", valid: isBackgroundSize },
	"background-position": {
		cssProperty: "backgroundPosition",
		valid: isBackgroundPosition,
	},
	"background-repeat": {
		cssProperty: "backgroundRepeat",
		valid: isEnum(["repeat", "repeat-x", "repeat-y", "no-repeat", "space", "round"]),
	},
	"border-width": { cssProperty: "borderWidth", valid: isSpaceSeparated(isLength, 4) },
	"border-style": {
		cssProperty: "borderStyle",
		valid: isSpaceSeparated(
			isEnum([
				"none",
				"solid",
				"dashed",
				"dotted",
				"double",
				"groove",
				"ridge",
				"inset",
				"outset",
			]),
			4,
		),
	},
	"border-color": { cssProperty: "borderColor", valid: isSpaceSeparated(isColor, 4) },
	"border-radius": {
		cssProperty: "borderRadius",
		valid: isSpaceSeparated(isLength, 4),
	},
	color: { cssProperty: "color", valid: isColor },
};

/**
 * Resolves an element's `styles` into real inline CSS: drops (and DEV-warns
 * on) any property not in `STYLE_RULES` or whose value fails its rule.
 * `context` is a path/id, used only in the warning message.
 *
 * `position: "absolute"` automatically gets `z-index: 5` — see the `StyleProp`
 * doc comment in `types.ts` for why that's not an author-settable value.
 */
export function resolveStyles(
	styles: Partial<Record<StyleProp, string>> | undefined,
	context: string,
): CSSProperties | undefined {
	if (styles == null) return undefined;

	const resolved: Record<string, string> = {};
	for (const [key, value] of Object.entries(styles)) {
		const rule = STYLE_RULES[key as StyleProp];
		if (!rule || value == null) {
			if (import.meta.env.DEV) {
				console.warn(`[sheet] ${context}: style "${key}" is not allowed`);
			}
			continue;
		}
		if (!rule.valid(value)) {
			if (import.meta.env.DEV) {
				console.warn(
					`[sheet] ${context}: style "${key}" has an invalid value "${value}"`,
				);
			}
			continue;
		}
		resolved[rule.cssProperty] = value;
	}

	if (resolved.position === "absolute") resolved.zIndex = "5";

	return Object.keys(resolved).length > 0 ? (resolved as CSSProperties) : undefined;
}

// --- `class` token allowlist ----------------------------------------------
//
// A sheet is user-authored, so — like `styles` — `class` is an allowlist. A
// token that names a `classes` bundle never reaches the DOM (it expands to
// inline style); every other token must be one of the curated `char-sheet-*`
// utilities, or `headerbar` (the single site-wide class a sheet may pull in).
// Anything else — an app utility, a global layout class, a token crafted to
// spoof chrome — is dropped with a DEV warning, never forwarded to the DOM.
// The `char-sheet-*` shape is checked by pattern, not against the closed list
// in `char-sheet.css`: a made-up `char-sheet-foo` simply has no rule behind
// it, exactly like any other unknown class.

const UTILITY_CLASS_RE = /^char-sheet-[a-z0-9-]+$/;

/** A curated `char-sheet-*` utility, or `headerbar`. */
export function isAllowedUtilityClass(token: string): boolean {
	return token === "headerbar" || UTILITY_CLASS_RE.test(token);
}

/**
 * Filters raw author class strings down to the tokens `isAllowedUtilityClass`
 * permits, DEV-warning on every drop. Each input string may itself hold
 * whitespace-separated tokens (a `class_when` key can), so every entry is
 * split and checked token by token. `context` is only used in the warning.
 */
export function filterUtilityClasses(raw: Iterable<string>, context: string): string[] {
	const out: string[] = [];
	for (const group of raw) {
		for (const token of group.split(/\s+/).filter(Boolean)) {
			if (isAllowedUtilityClass(token)) {
				out.push(token);
			} else if (import.meta.env.DEV) {
				console.warn(
					`[sheet] ${context}: class "${token}" is not a char-sheet-* utility or a classes bundle; dropped`,
				);
			}
		}
	}
	return out;
}

/**
 * Resolves an element's `class` + `styles` into `{ className, style }`.
 *
 * `class` tokens are split on whitespace: a token that names a `bundles` entry
 * (from `SheetSchema.classes`) contributes that bundle's properties; every
 * other token survives only if `filterUtilityClasses` allows it (a
 * `char-sheet-*` utility or `headerbar`) — anything else is dropped and
 * DEV-warned. The final inline style layers, per-property: earlier bundle <
 * later bundle < the element's own `styles`. The merged bag goes through
 * `resolveStyles`, so a bad value in a bundle is dropped and DEV-warned
 * exactly as an inline one would be.
 */
export function resolveElementStyles(
	classAttr: string | undefined,
	ownStyles: StyleBundle | undefined,
	bundles: Record<string, StyleBundle> | undefined,
	context: string,
): { className?: string; style?: CSSProperties } {
	const looseTokens: string[] = [];
	const merged: Record<string, string | undefined> = {};

	for (const token of classAttr?.split(/\s+/).filter(Boolean) ?? []) {
		const bundle = bundles?.[token];
		if (bundle) Object.assign(merged, bundle);
		else looseTokens.push(token);
	}
	const utilityClasses = filterUtilityClasses(looseTokens, context);
	if (ownStyles) Object.assign(merged, ownStyles);

	return {
		className: utilityClasses.length > 0 ? utilityClasses.join(" ") : undefined,
		style: resolveStyles(merged as StyleBundle, context),
	};
}

// --- Grid track lists (`columns` on `grid` / `repeater`) --------------------
//
// `grid-template-columns` is deliberately NOT a `StyleProp` above — its value
// grammar (minmax / repeat / calc / custom-property soup) is far too open to
// validate as one style property. Instead a `columns` array is checked here one
// ENTRY AT A TIME (each entry is one whole track token — never whitespace-split)
// against a small, closed track vocabulary, then joined into a
// `grid-template-columns` string. Anything outside it — notably `calc()`, which
// is where nested-expression injection lives — is dropped with a DEV warning.

const FR_RE = /^\d+(?:\.\d+)?fr$/;
const CHAR_SHEET_VAR_RE = /^var\(--char-sheet-[a-z0-9-]+\)$/i;
// repeat() count: a positive integer 1–50, or the auto keywords.
const REPEAT_COUNT_RE = /^(?:auto-fill|auto-fit|[1-9]|[1-4]\d|50)$/;
const TRACK_KEYWORDS = new Set(["auto", "min-content", "max-content"]);

/** A non-negative `<length-percentage>` (reuses the length rule, bars a leading `-`). */
const isTrackLength = (v: string) => v === "0" || (isLength(v) && !v.startsWith("-"));

/** Split `input` on `sep` (a comma, or any whitespace) at paren depth 0 only. */
function splitTopLevel(input: string, sep: "," | " "): string[] {
	const out: string[] = [];
	let depth = 0;
	let cur = "";
	for (const ch of input) {
		if (ch === "(") depth++;
		else if (ch === ")") depth = Math.max(0, depth - 1);
		if (depth === 0 && (sep === "," ? ch === "," : /\s/.test(ch))) {
			if (cur.trim()) out.push(cur.trim());
			cur = "";
		} else {
			cur += ch;
		}
	}
	if (cur.trim()) out.push(cur.trim());
	return out;
}

/** A fixed track breadth: length | `<n>fr` | auto/min-content/max-content | `var(--char-sheet-*)`. */
const isSizeToken = (t: string) =>
	isTrackLength(t) ||
	FR_RE.test(t) ||
	TRACK_KEYWORDS.has(t) ||
	CHAR_SHEET_VAR_RE.test(t);

/** `minmax(<size>, <size>)` — no nesting of `minmax` / `repeat` (matches CSS). */
function isMinmax(tok: string): boolean {
	const m = /^minmax\((.*)\)$/is.exec(tok);
	if (!m) return false;
	const args = splitTopLevel(m[1], ",");
	return args.length === 2 && args.every(isSizeToken);
}

/**
 * One grid track: a size token, a `minmax(...)`, or a
 * `repeat(<int 1–50 | auto-fill | auto-fit>, <size|minmax>+)`. `calc()` and
 * nested `repeat()` are intentionally rejected.
 */
function isTrackToken(raw: string): boolean {
	const tok = raw.trim();
	if (isSizeToken(tok) || isMinmax(tok)) return true;

	const r = /^repeat\((.*)\)$/is.exec(tok);
	if (r) {
		const args = splitTopLevel(r[1], ",");
		if (args.length !== 2 || !REPEAT_COUNT_RE.test(args[0])) return false;
		const tracks = splitTopLevel(args[1], " ");
		return tracks.length > 0 && tracks.every((t) => isSizeToken(t) || isMinmax(t));
	}
	return false;
}

/**
 * Validates a `columns` array (one whole track token per entry) and joins the
 * good entries into a `grid-template-columns` value. Returns `undefined` for an
 * empty or all-invalid list, so a bad `columns` falls back to the element's CSS
 * default (a helper class or the stylesheet fallback) instead of breaking the
 * layout. `context` is only used in the DEV warning.
 */
export function validateColumns(
	columns: readonly string[] | undefined,
	context: string,
): string | undefined {
	if (columns == null || columns.length === 0) return undefined;
	const good: string[] = [];
	for (const entry of columns) {
		if (isTrackToken(entry)) {
			good.push(entry.trim());
		} else if (import.meta.env.DEV) {
			console.warn(
				`[sheet] ${context}: grid column "${entry}" is not an allowed track size`,
			);
		}
	}
	return good.length > 0 ? good.join(" ") : undefined;
}
