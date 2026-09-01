import type { ReactNode } from "react";
import styles from "./FadeOut.module.css";

interface FadeOutProps {
	/** Show the content when true; fade it out when false. */
	active: boolean;
	/**
	 * Text announced to screen readers while `active`. Defaults to `children`
	 * when they're a plain string; pass explicitly when they aren't.
	 */
	announce?: string;
	className?: string;
	children: ReactNode;
}

/**
 * Renders `children` inline and fades them in/out based on `active`, with a
 * visually-hidden aria-live region so the change is announced. Drive `active`
 * with the `useFlash` hook for transient confirmations like a post-save
 * "Saved" indicator.
 */
export function FadeOut({ active, announce, className, children }: FadeOutProps) {
	const message = announce ?? (typeof children === "string" ? children : "");

	return (
		<>
			<span
				aria-hidden="true"
				className={`${styles.fade}${active ? ` ${styles.visible}` : ""}${
					className ? ` ${className}` : ""
				}`}
			>
				{children}
			</span>
			<output aria-live="polite" className="visually-hidden">
				{active ? message : ""}
			</output>
		</>
	);
}
