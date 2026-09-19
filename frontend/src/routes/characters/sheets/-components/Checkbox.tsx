import clsx from "clsx";
import type { CSSProperties } from "react";
import { useControlBinding } from "./sheet-values";

interface CheckboxProps {
	name: string;
	default?: boolean;
	className?: string;
	style?: CSSProperties;
}

/**
 * A single boolean field — just the control. Renders a checkbox in edit mode and
 * a read-only ✓ / — marker in display mode. Any label is a sibling `label`
 * element in the enclosing `group`, wired to the input by shared DOM id (see
 * `Group`); a repeater `header` cell above it is picked up as `aria-labelledby`.
 *
 * The value is bound to the sheet value store by `name`, scoped to the
 * element's position in the tree (see `sheet-values`).
 */
export function Checkbox({
	name,
	default: defaultValue,
	className,
	style,
}: CheckboxProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		boolean | undefined
	>(name, defaultValue);
	const checked = value === true;

	return (
		<div
			className={clsx("char-sheet-field", "char-sheet-field--checkbox", className)}
			style={style}
		>
			{mode === "display" ? (
				<span id={domId} className="char-sheet-value">
					{checked ? "✓" : "—"}
				</span>
			) : (
				<input
					id={domId}
					name={name}
					type="checkbox"
					checked={checked}
					onChange={(e) => setValue(e.target.checked)}
					aria-labelledby={ariaLabelledBy}
				/>
			)}
		</div>
	);
}
