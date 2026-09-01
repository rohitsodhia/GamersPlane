import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Transient boolean that flips on when `flash()` is called and back off after
 * `duration` ms. Repeat calls re-arm the timer; the timer is cleared on
 * unmount. Drives fleeting post-action confirmations such as a "Saved"
 * indicator that fades out (pair with the `<FadeOut>` component).
 */
export function useFlash(duration = 3000) {
	const [active, setActive] = useState(false);
	const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	const flash = useCallback(() => {
		clearTimeout(timer.current);
		setActive(true);
		timer.current = setTimeout(() => setActive(false), duration);
	}, [duration]);

	useEffect(() => () => clearTimeout(timer.current), []);

	return [active, flash] as const;
}
