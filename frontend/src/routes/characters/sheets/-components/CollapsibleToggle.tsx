import clsx from "clsx";
import type { CSSProperties } from "react";
import { useCollapsibleToggle } from "./collapsible-scope";

interface CollapsibleToggleProps {
	target: string;
	label: string;
	className?: string;
	style?: CSSProperties;
}

/**
 * The external trigger for a `collapsible`. Sits anywhere in the same
 * disclosure scope as its target (commonly a sibling, or another cell in the
 * same repeater row) and flips it open/closed. Rendered as a text button,
 * styled to read as a link by default.
 */
export function CollapsibleToggle({
	target,
	label,
	className,
	style,
}: CollapsibleToggleProps) {
	const { open, bodyId, toggle } = useCollapsibleToggle(target);
	return (
		<button
			type="button"
			className={clsx("char-sheet-collapsible-toggle", className)}
			style={style}
			aria-expanded={open}
			aria-controls={bodyId}
			onClick={toggle}
		>
			{label}
		</button>
	);
}
