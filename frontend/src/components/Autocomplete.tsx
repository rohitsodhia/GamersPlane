import clsx from "clsx";
import type { CSSProperties } from "react";
import { useLayoutEffect, useRef, useState } from "react";
import { useFilter } from "react-aria";
import {
	Input,
	Menu,
	MenuItem,
	Autocomplete as RACAutocomplete,
	SearchField,
} from "react-aria-components";

// The HTML `size` attribute (default 20) sets an <input>'s intrinsic width in
// characters. A percentage CSS width can't override that for the grid's
// intrinsic-sizing pass below (percentages fall back to intrinsic size there),
// so the sizer span would lose to this default. 1 is the smallest legal value
// (the HTML spec requires >= 1) — it neutralizes the attribute's influence;
// the actual rendered width still comes from CSS width: 100% once the grid
// column is sized.
const MIN_INPUT_SIZE = 1;

export function Autocomplete<T>({
	id,
	items,
	getId,
	getLabel,
	onAction,
	onInputChange,
	inputValue: controlledValue,
	placeholder,
	onClear,
	className,
}: {
	id: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	// Fired when an item is picked. By default the picked item's label stays in
	// the box (single-value picker). `controls.clear()` empties it — call it from
	// pickers that accumulate a list and want a fresh input for the next pick.
	onAction: (id: string, controls: { clear: () => void }) => void;
	onInputChange?: (value: string) => void;
	// When supplied, the caller drives the input value (and must keep it in sync
	// via onInputChange). Left undefined, the input stays uncontrolled.
	inputValue?: string;
	placeholder?: string;
	// Fired when the user empties the box themselves (typing/backspacing to "")
	// rather than picking an item — lets a single-value filter clear itself
	// without a dedicated "All ..." menu item.
	onClear?: () => void;
	/** Extra classes on the wrapper (the "autocomplete" default class is kept). */
	className?: string;
}) {
	const { contains } = useFilter({ sensitivity: "base" });
	const [isOpen, setIsOpen] = useState(false);
	const [uncontrolledValue, setUncontrolledValue] = useState("");
	const inputValue = controlledValue ?? uncontrolledValue;

	// When onInputChange is supplied the caller is feeding an already-filtered
	// list from the server, so RAC must not filter again (no `filter` prop).
	// Without it, `items` is a static list RAC filters locally by substring.
	const isAsync = onInputChange !== undefined;

	// Don't render the menu when there's nothing to show. For the async case the
	// caller already filtered, so `items` is the visible set. For the local case
	// mirror RAC's substring filter to know whether anything would render.
	const hasItems = isAsync
		? items.length > 0
		: items.some((item) => contains(getLabel(item), inputValue));

	// Measure the (hidden) sizer's widest row and feed it back in as a CSS
	// variable, rather than leaning on the grid-overlap trick .react-aria-Select
	// uses: an <input>'s own default intrinsic width (the `size` attribute,
	// 20 by default) still out-sizes that trick for the field's auto-computed
	// track width, even at size=1 — Chrome's `type="search"` reserves extra
	// space for its native clear button regardless. Measuring directly
	// sidesteps that rather than fighting more browser-specific quirks.
	const sizerRef = useRef<HTMLSpanElement>(null);
	const [measuredWidth, setMeasuredWidth] = useState<number | null>(null);
	// items/placeholder aren't referenced directly below — they're read back via
	// the DOM through sizerRef — but re-measuring needs to re-run whenever they
	// (and so the sizer's rendered content) change.
	// biome-ignore lint/correctness/useExhaustiveDependencies: see above
	useLayoutEffect(() => {
		const rows = sizerRef.current?.querySelectorAll<HTMLElement>(
			".autocomplete-sizer-row",
		);
		if (!rows || rows.length === 0) return;
		const widest = Math.max(
			...[...rows].map((row) => row.getBoundingClientRect().width),
		);
		setMeasuredWidth(Math.ceil(widest));
	}, [items, placeholder]);

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: closes the menu when focus leaves it
		<div
			className={clsx("autocomplete", className)}
			style={
				{
					"--autocomplete-measured-width":
						measuredWidth == null ? undefined : `${measuredWidth}px`,
				} as CSSProperties
			}
			onBlur={(e) => {
				if (!e.currentTarget.contains(e.relatedTarget)) setIsOpen(false);
			}}
		>
			<RACAutocomplete
				filter={isAsync ? undefined : contains}
				inputValue={inputValue}
				onInputChange={(value) => {
					setUncontrolledValue(value);
					onInputChange?.(value);
					if (value === "") onClear?.();
				}}
			>
				<SearchField id={id} onFocus={() => setIsOpen(true)}>
					<Input
						placeholder={placeholder}
						size={MIN_INPUT_SIZE}
						onKeyDown={() => setIsOpen(true)}
					/>
				</SearchField>
				{/* Hidden sizer: mirrors the Input's box for every option (plus the
				    placeholder), measured in a layout effect above so the field
				    grows to fit the widest one, native `<select>` style. A consumer
				    that sets `--rac-autocomplete-width` in its own stylesheet opts
				    back into a fixed width. */}
				<span className="autocomplete-sizer" aria-hidden="true" ref={sizerRef}>
					{placeholder && <span className="autocomplete-sizer-row">{placeholder}</span>}
					{items.map((item) => (
						<span key={getId(item)} className="autocomplete-sizer-row">
							{getLabel(item)}
						</span>
					))}
				</span>
				{isOpen && hasItems && (
					<Menu
						items={items}
						onAction={(key) => {
							// Behave like an input: keep the picked item's label in the box.
							// The caller can override via controls.clear(). Controlled callers
							// drive the value themselves through onInputChange.
							if (controlledValue === undefined) {
								const picked = items.find((item) => getId(item) === String(key));
								if (picked) setUncontrolledValue(getLabel(picked));
							}
							onAction(key as string, {
								clear: () => {
									setUncontrolledValue("");
									onInputChange?.("");
								},
							});
							setIsOpen(false);
						}}
					>
						{(item) => (
							<MenuItem id={getId(item)} textValue={getLabel(item)}>
								{getLabel(item)}
							</MenuItem>
						)}
					</Menu>
				)}
			</RACAutocomplete>
		</div>
	);
}
