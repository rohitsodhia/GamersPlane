import clsx from "clsx";
import { type CSSProperties, type ReactNode, useId } from "react";
import { useRollable } from "./Rollable";
import { FieldDomIdContext } from "./sheet-values";
import type { RollSpec } from "./types";

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
	/** Makes the whole group a rollable row (display mode only; see `RollSpec`). */
	roll?: RollSpec;
	/** The group's first `label` / `text` child's text: the roll's default reason. */
	rollReason?: string;
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
export function Group({
	className,
	style,
	labelFor,
	roll,
	rollReason,
	children,
}: GroupProps) {
	const id = useId();
	return (
		<FieldDomIdContext.Provider value={{ id, ownerName: labelFor }}>
			{roll == null ? (
				<div className={clsx("char-sheet-group", className)} style={style}>
					{children}
				</div>
			) : (
				<RollableGroup
					roll={roll}
					rollReason={rollReason ?? ""}
					className={className}
					style={style}
				>
					{children}
				</RollableGroup>
			)}
		</FieldDomIdContext.Provider>
	);
}

/**
 * A group with a `roll`: the whole row is the click target (forwarded to the
 * dice icon's action, except for clicks on its interactive children), and the
 * icon sits on the group's own box. In edit mode `useRollable` yields nothing
 * and this is the plain group.
 */
function RollableGroup({
	roll,
	rollReason,
	className,
	style,
	children,
}: {
	roll: RollSpec;
	rollReason: string;
	className?: string;
	style?: CSSProperties;
	children?: ReactNode;
}) {
	const rollable = useRollable(roll, rollReason);
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the click is a pointer convenience over the icon button, which is the keyboard / assistive-tech route
		// biome-ignore lint/a11y/useKeyWithClickEvents: see above
		<div
			className={clsx("char-sheet-group", rollable?.className, className)}
			style={{ ...style, ...rollable?.style }}
			onClick={rollable?.onClick}
		>
			{children}
			{rollable?.icon}
		</div>
	);
}
