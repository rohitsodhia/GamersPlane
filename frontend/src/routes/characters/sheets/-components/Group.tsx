import clsx from "clsx";
import { type CSSProperties, type ReactNode, useId } from "react";
import { FieldDomIdContext } from "./sheet-values";

interface GroupProps {
	className?: string;
	style?: CSSProperties;
	/**
	 * `name` of the child control the group's `label`(s) wire to. The renderer
	 * works this out from the schema (the sole bound control, or the one flagged
	 * `attach_label`); undefined when it can't be determined, in which case the
	 * labels render without an association.
	 */
	labelFor?: string;
	children?: ReactNode;
}

/**
 * A generic grouping wrapper. Mints one DOM id and publishes it (with the
 * owning control's `name`) so a sibling `label` and its `input` can be wired
 * together without the label being a prop on the input. Layout is entirely a
 * matter of the `class`/`styles` the author puts on the group — including,
 * e.g., a `background-image` with `position: "relative"` so absolutely
 * positioned fields inside it line up against it.
 */
export function Group({ className, style, labelFor, children }: GroupProps) {
	const id = useId();
	return (
		<FieldDomIdContext.Provider value={{ id, ownerName: labelFor }}>
			<div className={clsx("char-sheet-group", className)} style={style}>
				{children}
			</div>
		</FieldDomIdContext.Provider>
	);
}
