import type { PaletteColor } from "#/components/tiptap/tiptap-extension/color-palette";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";

import "#/components/tiptap/tiptap-ui/color-swatches/color-swatches.scss";

/** A grid of named color buttons; the custom picker sits beside it in the popover. */
export function ColorSwatches({
	colors,
	activeColor,
	onPick,
}: {
	colors: readonly PaletteColor[];
	/** The color at the selection, to mark its swatch. */
	activeColor?: string | null;
	onPick: (color: string) => void;
}) {
	const active = activeColor?.toLowerCase();
	return (
		<div className="tiptap-color-swatches">
			{colors.map((color) => (
				<Button
					key={color.value}
					type="button"
					variant="ghost"
					className="tiptap-color-swatch"
					aria-label={color.name}
					tooltip={color.name}
					aria-pressed={active === color.value}
					data-active-state={active === color.value ? "on" : "off"}
					style={{ backgroundColor: color.value }}
					onClick={() => onPick(color.value)}
				/>
			))}
		</div>
	);
}
