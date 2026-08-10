import { useState } from "react";
import { useResizeObserver } from "#/lib/use-resize-observer";

/**
 * Measures a .headerbar element's doubled margin-inline-start, in resolved
 * px, since it can be sized in ems that resolve differently per heading.
 * Attach `ref` to the headerbar; apply the returned `margin` to whichever
 * other elements need to line up with it (marginInlineStart, marginInlineEnd,
 * or marginInline for both), regardless of their position relative to it.
 */
export function useHbMargined<T extends HTMLElement>() {
	const [margin, setMargin] = useState(0);
	const [overPadding, setOverPadding] = useState(0);

	const ref = useResizeObserver<T>((el) => {
		const cs = getComputedStyle(el);
		setMargin(parseFloat(cs.marginInlineStart) * 2);
		setOverPadding(parseFloat(cs.marginInlineStart) - parseFloat(cs.marginInlineStart));
	});

	return { ref, margin, overPadding };
}
