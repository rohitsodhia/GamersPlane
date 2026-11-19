const ALLOWED_LINK_SCHEMES: ReadonlySet<string> = new Set(["http", "https", "mailto"]);

// Tiptap's own `isAllowedUri` always admits its built-in list (ftp, tel, sms, ...)
// and `protocols` can only add to it, so narrowing needs this override. Scheme-less
// values (relative paths, bare hosts) are still allowed, as with the default.
export function isAllowedLinkUri(uri: string | undefined): boolean {
	if (!uri) return true;
	// Browsers ignore whitespace and control characters inside a scheme (`java\tscript:`).
	// biome-ignore lint/suspicious/noControlCharactersInRegex: that is the point
	const compact = uri.replace(/[\s\u0000-\u001f]/g, "");
	const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(compact)?.[1];
	return scheme === undefined || ALLOWED_LINK_SCHEMES.has(scheme.toLowerCase());
}
