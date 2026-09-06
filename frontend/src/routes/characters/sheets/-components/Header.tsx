import clsx from "clsx";
import type { CSSProperties } from "react";

interface HeaderProps {
	text: string;
	/** Adds the site-wide `headerbar` class (the orange ribbon heading style). */
	headerbar?: boolean;
	className?: string;
	style?: CSSProperties;
}

/**
 * A section heading. Carries no value and reads nothing from the value store,
 * so it has no edit / display split. `headerbar` opts into the same heading
 * style routes use elsewhere in the app; without it this is a plain `<h2>`
 * for sheets that want their own heading styling via `class`.
 */
export function Header({ text, headerbar, className, style }: HeaderProps) {
	return (
		<h2 className={clsx(headerbar && "headerbar", className)} style={style}>
			{text}
		</h2>
	);
}
