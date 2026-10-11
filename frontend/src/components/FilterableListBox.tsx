import clsx from "clsx";
import type { CSSProperties } from "react";
import { useFilter } from "react-aria";
import {
	Autocomplete,
	Input,
	Label,
	ListBox,
	ListBoxItem,
	SearchField,
	type Selection,
} from "react-aria-components";

// A text input that filters a persistent ListBox sitting beneath it. Distinct
// from `Autocomplete` (which wraps a Menu for combobox-style single-value
// picking where the picked label returns to the input) — here the list stays
// visible and the input only narrows it.
//
// Two selection modes, picked by the `selectionMode` prop:
// - "single" (default): one item at a time. `selectedId` / `onChange(id | null)`.
// - "multiple": a checklist; clicking a row toggles it and selected rows show a
//   checkmark. `selectedIds` / `onChange(ids)`. Selections hidden by the current
//   filter stay selected: RAC keeps the full `selectedKeys` set and only toggles
//   the clicked key, and `selectionFromKeys` covers the one case (select-all) where
//   it reports something other than a delta.
//
// The input swallows Enter so that a list embedded in a <form> doesn't submit it.

type CommonProps<T> = {
	id?: string;
	label: string;
	// Keep the label for screen readers but don't show it, where context makes it obvious.
	hideLabel?: boolean;
	placeholder?: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	// Extra classes for an item's row, to mark some items apart from the rest.
	getClassName?: (item: T) => string | undefined;
	emptyState?: string;
	// Cap the visible list at roughly this many rows before it scrolls. Rows are
	// measured in `--rac-list-item-height` units (see rac.css); leave unset to
	// use the shared `--rac-list-max-height` default.
	maxVisibleItems?: number;
};

type SingleProps = {
	selectionMode?: "single";
	selectedId: string | null;
	onChange: (id: string | null) => void;
	disallowEmptySelection?: boolean;
};

type MultipleProps = {
	selectionMode: "multiple";
	selectedIds: string[];
	onChange: (ids: string[]) => void;
};

export type FilterableListBoxProps<T> = CommonProps<T> & (SingleProps | MultipleProps);

/**
 * Turns RAC's reported selection into the id list for "multiple" mode. RAC
 * reports the full selected set (hidden-by-filter keys included), so this is a
 * plain conversion, except that "all" (Ctrl+A) is expanded to every item id.
 */
export function selectionFromKeys(keys: Selection, allIds: string[]): string[] {
	return keys === "all" ? allIds : [...keys].map(String);
}

export function FilterableListBox<T>(props: FilterableListBoxProps<T>) {
	const {
		id,
		label,
		hideLabel,
		placeholder,
		items,
		getId,
		getLabel,
		getClassName,
		emptyState = "No matches",
		maxVisibleItems,
	} = props;
	const { contains } = useFilter({ sensitivity: "base" });

	const selectionProps =
		props.selectionMode === "multiple"
			? ({
					selectionMode: "multiple",
					selectedKeys: props.selectedIds,
					onSelectionChange: (keys: Selection) =>
						props.onChange(selectionFromKeys(keys, items.map(getId))),
				} as const)
			: ({
					selectionMode: "single",
					disallowEmptySelection: props.disallowEmptySelection,
					selectedKeys: props.selectedId === null ? [] : [props.selectedId],
					onSelectionChange: (keys: Selection) => {
						const [key] = [...keys];
						props.onChange(key == null ? null : String(key));
					},
				} as const);

	return (
		<div
			className={clsx(
				"filterable-listbox",
				props.selectionMode === "multiple" && "filterable-listbox--multiple",
			)}
			style={
				maxVisibleItems == null
					? undefined
					: ({
							"--rac-list-max-height": `calc(${maxVisibleItems} * var(--rac-list-item-height))`,
						} as CSSProperties)
			}
		>
			<Autocomplete filter={contains}>
				<SearchField
					id={id}
					onKeyDown={(event) => {
						// Don't let Enter submit an enclosing <form>. RAC's Autocomplete
						// already prevents it today; this keeps that from depending on it.
						if (event.key === "Enter") event.preventDefault();
					}}
				>
					<Label className={hideLabel ? "visually-hidden" : undefined}>{label}</Label>
					<Input placeholder={placeholder} />
				</SearchField>
				<ListBox
					aria-label={label}
					items={items}
					renderEmptyState={() => emptyState}
					{...selectionProps}
				>
					{(item) => (
						<ListBoxItem
							id={getId(item)}
							textValue={getLabel(item)}
							// A className replaces RAC's default class, which rac.css styles.
							className={clsx("react-aria-ListBoxItem", getClassName?.(item))}
						>
							{getLabel(item)}
						</ListBoxItem>
					)}
				</ListBox>
			</Autocomplete>
		</div>
	);
}
