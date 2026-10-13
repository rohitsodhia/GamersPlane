import clsx from "clsx";
import type { CSSProperties } from "react";
import { Rollable } from "./Rollable";
import { useLabelDomId } from "./sheet-values";
import type { RollSpec } from "./types";

interface LabelProps {
	text: string;
	roll?: RollSpec;
	className?: string;
	style?: CSSProperties;
}

/**
 * A `<label>` for a control elsewhere in the same `group`. It reads the group's
 * DOM id from context for `htmlFor`; outside a group it renders with none.
 */
export function Label({ text, roll, className, style }: LabelProps) {
	const htmlFor = useLabelDomId();
	const render = (dom: { className?: string; style?: CSSProperties }) => (
		<label
			htmlFor={htmlFor}
			className={clsx("char-sheet-label", dom.className)}
			style={dom.style}
		>
			{text}
		</label>
	);

	if (roll == null) return render({ className, style });
	return (
		<Rollable
			roll={roll}
			fallbackReason={text}
			className={className}
			style={style}
			isLabel
		>
			{render}
		</Rollable>
	);
}
