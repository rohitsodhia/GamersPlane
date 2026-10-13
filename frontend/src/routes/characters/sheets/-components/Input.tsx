import clsx from "clsx";
import type { CSSProperties } from "react";
import { LiveError } from "./LiveError";
import { useControlBinding, useLiveField } from "./sheet-values";

interface InputProps {
	name: string;
	maxlength?: number;
	default?: string | number;
	/** Editable in display mode too, saving on blur / Enter (see `useLiveField`). */
	live?: boolean;
	className?: string;
	style?: CSSProperties;
}

/**
 * A single-line scalar field — just the control. Any label is a sibling `label`
 * element in the enclosing `group`, which wires the two together (see `Group`).
 *
 * The value is bound to the sheet value store by `name`, scoped to the field's
 * position in the tree (see `sheet-values`). In display mode it renders the
 * stored value as static text instead of an input, unless it is `live` and the
 * viewer can edit it: then it stays an input and saves on blur or Enter.
 */
export function Input({
	name,
	maxlength,
	default: defaultValue,
	live: liveField,
	className,
	style,
}: InputProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		string | undefined
	>(name, defaultValue != null ? String(defaultValue) : undefined);
	const live = useLiveField(name, liveField, value);

	if (mode === "display" && !live.editable) {
		return (
			<span id={domId} className={clsx("char-sheet-value", className)} style={style}>
				{value ?? ""}
			</span>
		);
	}

	return (
		<>
			<input
				id={domId}
				name={name}
				type="text"
				className={
					clsx(live.saving && "char-sheet-live--saving", className) || undefined
				}
				style={style}
				maxLength={maxlength}
				value={value ?? ""}
				onChange={(e) => {
					if (live.editable) live.begin();
					setValue(e.target.value);
				}}
				onBlur={() => live.editable && live.commit(value ?? "")}
				onKeyDown={(e) => {
					if (e.key === "Enter" && live.editable) live.commit(value ?? "");
				}}
				aria-labelledby={ariaLabelledBy}
				aria-busy={live.saving || undefined}
				aria-invalid={live.error !== null || undefined}
			/>
			<LiveError error={live.error} />
		</>
	);
}
