import clsx from "clsx";
import type { CSSProperties } from "react";
import { useControlBinding } from "./sheet-values";

interface TextareaProps {
	name: string;
	/** Visible row count; forwarded to the `<textarea>`'s `rows`. */
	rows?: number;
	/** Forwarded to the `<textarea>`'s `maxLength`. */
	maxlength?: number;
	default?: string;
	className?: string;
	style?: CSSProperties;
}

/**
 * A multi-line text field — just the control. Any label is a sibling `label`
 * element in the enclosing `group`, which wires the two together (see `Group`).
 *
 * The value is bound to the sheet value store by `name`, scoped to the field's
 * position in the tree (see `sheet-values`). In display mode it renders the
 * stored text with newlines preserved instead of a textarea.
 */
export function Textarea({
	name,
	rows,
	maxlength,
	default: defaultValue,
	className,
	style,
}: TextareaProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		string | undefined
	>(name, defaultValue);

	return mode === "display" ? (
		<span
			id={domId}
			className={clsx("char-sheet-value", "char-sheet-value--multiline", className)}
			style={style}
		>
			{value ?? ""}
		</span>
	) : (
		<textarea
			id={domId}
			name={name}
			className={clsx("char-sheet-textarea", className)}
			style={style}
			rows={rows}
			maxLength={maxlength}
			value={value ?? ""}
			onChange={(e) => setValue(e.target.value)}
			aria-labelledby={ariaLabelledBy}
		/>
	);
}
