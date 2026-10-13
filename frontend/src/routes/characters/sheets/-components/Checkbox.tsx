import clsx from "clsx";
import type { CSSProperties } from "react";
import { LiveError } from "./LiveError";
import { useControlBinding, useLiveField } from "./sheet-values";

interface CheckboxProps {
	name: string;
	default?: boolean;
	/** Editable in display mode too, saving on change (see `useLiveField`). */
	live?: boolean;
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
	live: liveField,
	className,
	style,
}: CheckboxProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		boolean | undefined
	>(name, defaultValue);
	const live = useLiveField(name, liveField, value);
	const checked = value === true;

	return (
		<div
			className={clsx("char-sheet-field", "char-sheet-field--checkbox", className)}
			style={style}
		>
			{mode === "display" && !live.editable ? (
				<span id={domId} className="char-sheet-value">
					{checked ? "✓" : "—"}
				</span>
			) : (
				<>
					<input
						id={domId}
						name={name}
						type="checkbox"
						className={live.saving ? "char-sheet-live--saving" : undefined}
						checked={checked}
						onChange={(e) => {
							const next = e.target.checked;
							if (live.editable) live.begin();
							setValue(next);
							if (live.editable) live.commit(next);
						}}
						aria-labelledby={ariaLabelledBy}
						aria-busy={live.saving || undefined}
						aria-invalid={live.error !== null || undefined}
					/>
					<LiveError error={live.error} />
				</>
			)}
		</div>
	);
}
