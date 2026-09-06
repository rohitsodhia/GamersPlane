import clsx from "clsx";
import type { CSSProperties } from "react";
import { useControlBinding } from "./sheet-values";

interface InputProps {
	name: string;
	maxlength?: number;
	default?: string | number;
	className?: string;
	style?: CSSProperties;
}

/**
 * A single-line scalar field — just the control. Any label is a sibling `label`
 * element in the enclosing `group`, which wires the two together (see `Group`).
 *
 * The value is bound to the sheet value store by `name`, scoped to the field's
 * position in the tree (see `sheet-values`). In display mode it renders the
 * stored value as static text instead of an input.
 */
export function Input({
	name,
	maxlength,
	default: defaultValue,
	className,
	style,
}: InputProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		string | undefined
	>(name, defaultValue != null ? String(defaultValue) : undefined);

	return mode === "display" ? (
		<span id={domId} className={clsx("char-sheet-value", className)} style={style}>
			{value ?? ""}
		</span>
	) : (
		<input
			id={domId}
			name={name}
			type="text"
			className={className}
			style={style}
			maxLength={maxlength}
			value={value ?? ""}
			onChange={(e) => setValue(e.target.value)}
			aria-labelledby={ariaLabelledBy}
		/>
	);
}
