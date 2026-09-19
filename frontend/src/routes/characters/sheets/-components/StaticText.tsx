import clsx from "clsx";
import type { CSSProperties } from "react";

interface StaticTextProps {
	text: string;
	className?: string;
	style?: CSSProperties;
}

/**
 * The literal branch of the `text` element (dispatched from `Text.tsx`): a
 * non-interactive line of text — a column header inside a `grid` header, a note
 * between fields, a row label. Carries no value and reads nothing from the value
 * store, so it has no edit / display split.
 */
export function StaticText({ text, className, style }: StaticTextProps) {
	return (
		<span className={clsx("char-sheet-text", className)} style={style}>
			{text}
		</span>
	);
}
