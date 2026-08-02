import { useLayoutEffect, useRef, useState } from "react";

/**
 * Measures a .headerbar element's doubled margin-inline-start, in resolved
 * px, since it can be sized in ems that resolve differently per heading.
 * Attach `ref` to the headerbar; apply the returned `margin` to whichever
 * other elements need to line up with it (marginInlineStart, marginInlineEnd,
 * or marginInline for both), regardless of their position relative to it.
 */
export function useHbMargined<T extends HTMLElement>() {
	const ref = useRef<T>(null);
	const [margin, setMargin] = useState(0);

	useLayoutEffect(() => {
		const el = ref.current;
		if (!el) return;

		const measure = () => {
			const cs = getComputedStyle(el);
			setMargin(parseFloat(cs.marginInlineStart) * 2);
		};

		measure();

		const observer = new ResizeObserver(measure);
		observer.observe(el);
		return () => observer.disconnect();
	}, []);

	return { ref, margin };
}
