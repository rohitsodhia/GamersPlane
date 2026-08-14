import { useLayoutEffect, useRef } from "react";

/**
 * Observes an element's size and invokes `onResize` on mount and whenever
 * it changes. `onResize` is read from a ref internally, so passing a new
 * function each render does not tear down and recreate the observer.
 */
export function useResizeObserver<T extends HTMLElement>(onResize: (el: T) => void) {
	const ref = useRef<T>(null);
	const onResizeRef = useRef(onResize);
	onResizeRef.current = onResize;

	useLayoutEffect(() => {
		const el = ref.current;
		if (!el) return;

		const measure = () => onResizeRef.current(el);
		measure();

		const observer = new ResizeObserver(measure);
		observer.observe(el);
		return () => observer.disconnect();
	}, []);

	return ref;
}
