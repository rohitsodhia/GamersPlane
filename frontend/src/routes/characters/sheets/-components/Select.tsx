import clsx from "clsx";
import type { CSSProperties } from "react";
import { Select as RACSelect } from "#/components/Select";
import { useControlBinding } from "./sheet-values";
import type { SelectOption } from "./types";

interface SelectProps {
	name: string;
	values: SelectOption[];
	default?: string;
	className?: string;
	style?: CSSProperties;
}

type NormalizedOption = { value: string; label: string };

// Internal key for the "nothing chosen" row. RAC's Select has no native blank
// `<option>`, so an unset field needs a real list item to select; its id must
// not collide with a real option value, hence the sentinel. It maps to "" at
// every boundary (stored value, `default`, display lookup).
const BLANK = "\x00blank";

// Label for the blank row: a non-breaking space, not "". An empty label leaves
// the menu item with no line box, so it collapses to just its vertical padding.
const BLANK_LABEL = " ";

const normalize = (v: SelectOption): NormalizedOption =>
	typeof v === "string" ? { value: v, label: v } : v;

/**
 * A single-choice dropdown — just the control. Any label is a sibling `label`
 * element in the enclosing `group`, which wires the two together (see `Group`).
 *
 * `values` entries are either a bare string (value === label) or a
 * `{ value, label }` pair. A blank row is prepended unless `default` selects
 * one, so the field can be left / set back to unset. The chosen value is bound
 * to the sheet value store by `name`, scoped to the field's position in the tree
 * (see `sheet-values`). In display mode it renders the matching label as static
 * text.
 */
export function Select({
	name,
	values,
	default: defaultValue,
	className,
	style,
}: SelectProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		string | undefined
	>(name, defaultValue);

	const options = values.map(normalize);

	if (
		import.meta.env.DEV &&
		defaultValue != null &&
		defaultValue !== "" &&
		!options.some((o) => o.value === defaultValue)
	) {
		console.warn(
			`[sheet] select "${name}": default "${defaultValue}" is not one of its values`,
		);
	}

	if (mode === "display") {
		const label = options.find((o) => o.value === value)?.label ?? "";
		return (
			<span id={domId} className={clsx("char-sheet-value", className)} style={style}>
				{label}
			</span>
		);
	}

	const items =
		defaultValue == null || defaultValue === ""
			? [{ value: BLANK, label: BLANK_LABEL }, ...options]
			: options;

	return (
		<RACSelect
			id={domId}
			className={clsx("char-sheet-select", className)}
			style={style}
			items={items}
			getId={(o) => o.value}
			getLabel={(o) => o.label}
			selectedId={value == null || value === "" ? BLANK : value}
			onChange={(id) => setValue(id === BLANK ? "" : id)}
			ariaLabelledBy={ariaLabelledBy}
		/>
	);
}
