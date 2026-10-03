import clsx from "clsx";
import { type ReactNode, useEffect, useState } from "react";
import styles from "./DismissibleBanner.module.css";

const STORAGE_PREFIX = "gp:dismissed-banner:";

/**
 * A `.banner` with an × that hides it, remembered in localStorage under
 * `storageKey`. The server renders it shown; a dismissed banner is hidden once
 * the browser has read the stored flag.
 */
export function DismissibleBanner({
	storageKey,
	className,
	children,
}: {
	storageKey: string;
	className?: string;
	children: ReactNode;
}) {
	const [dismissed, setDismissed] = useState(false);

	useEffect(() => {
		try {
			setDismissed(localStorage.getItem(STORAGE_PREFIX + storageKey) !== null);
		} catch {
			// Storage blocked: the banner just stays visible.
		}
	}, [storageKey]);

	if (dismissed) {
		return null;
	}

	return (
		<div className={clsx("banner", styles["dismissible-banner"], className)}>
			<div>{children}</div>
			<button
				type="button"
				className={styles["dismiss"]}
				aria-label="Hide this message"
				title="Hide this message"
				onClick={() => {
					setDismissed(true);
					try {
						localStorage.setItem(STORAGE_PREFIX + storageKey, "1");
					} catch {
						// Hidden for this visit only.
					}
				}}
			>
				&times;
			</button>
		</div>
	);
}
