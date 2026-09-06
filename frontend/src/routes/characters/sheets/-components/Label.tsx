import clsx from "clsx";
import type { CSSProperties } from "react";
import { useLabelDomId } from "./sheet-values";

interface LabelProps {
	text: string;
	className?: string;
	style?: CSSProperties;
}

/**
 * A `<label>` for a control elsewhere in the same `group`. It reads the group's
 * DOM id from context for `htmlFor`; outside a group it renders with none.
 */
export function Label({ text, className, style }: LabelProps) {
	const htmlFor = useLabelDomId();
	return (
		<label
			htmlFor={htmlFor}
			className={clsx("char-sheet-label", className)}
			style={style}
		>
			{text}
		</label>
	);
}
