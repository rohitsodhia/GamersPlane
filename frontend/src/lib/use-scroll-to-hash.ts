import { useLocation } from "@tanstack/react-router";
import { useEffect } from "react";

/**
 * Scrolls to the element matching the current URL hash once it's in the DOM.
 * Needed because these routes render client-only (`ssr: false` under the SPA
 * build): TanStack Router's built-in hash scrollIntoView fires against the
 * pending fallback before the target element exists and never retries once
 * it mounts. Pass the data the target element depends on as `deps` so this
 * re-runs once that data (and the element) is actually rendered.
 *
 * On a fresh document load (not a client-side nav) our custom fonts are still
 * loading and swap in via `font-display: swap`, reflowing post text below the
 * fold after we've already scrolled. So we scroll again once fonts settle.
 *
 * Pair with `scroll-margin-top` on the target element(s) to offset for the
 * fixed header, since scrollIntoView respects it natively.
 */
export function useScrollToHash(deps: unknown[]) {
	const hash = useLocation({ select: (location) => location.hash });

	useEffect(() => {
		if (!hash) return;
		document.getElementById(hash)?.scrollIntoView();
		document.fonts.ready.then(() => {
			document.getElementById(hash)?.scrollIntoView();
		});
	}, [hash, ...deps]);
}
