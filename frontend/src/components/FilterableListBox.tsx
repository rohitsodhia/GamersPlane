import type { CSSProperties } from "react";
import { useFilter } from "react-aria";
import {
	Autocomplete,
	Input,
	Label,
	ListBox,
	ListBoxItem,
	SearchField,
} from "react-aria-components";

// A text input that filters a persistent, single-select ListBox sitting beneath
// it. Distinct from `Autocomplete` (which wraps a Menu for combobox-style
// single-value picking where the picked label returns to the input) — here the
// list stays visible and the input only narrows it.
export function FilterableListBox<T>({
	id,
	label,
	placeholder,
	items,
	getId,
	getLabel,
	selectedId,
	onChange,
	disallowEmptySelection,
	emptyState = "No matches",
	maxVisibleItems,
}: {
	id?: string;
	label: string;
	placeholder?: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	selectedId: string | null;
	onChange: (id: string | null) => void;
	disallowEmptySelection?: boolean;
	emptyState?: string;
	// Cap the visible list at roughly this many rows before it scrolls. Rows are
	// measured in `--rac-list-item-height` units (see rac.css); leave unset to
	// use the shared `--rac-list-max-height` default.
	maxVisibleItems?: number;
}) {
	const { contains } = useFilter({ sensitivity: "base" });

	return (
		<div
			className="filterable-listbox"
			style={
				maxVisibleItems == null
					? undefined
					: ({
							"--rac-list-max-height": `calc(${maxVisibleItems} * var(--rac-list-item-height))`,
						} as CSSProperties)
			}
		>
			<Autocomplete filter={contains}>
				<SearchField id={id}>
					<Label>{label}</Label>
					<Input placeholder={placeholder} />
				</SearchField>
				<ListBox
					aria-label={label}
					items={items}
					selectionMode="single"
					disallowEmptySelection={disallowEmptySelection}
					selectedKeys={selectedId === null ? [] : [selectedId]}
					renderEmptyState={() => emptyState}
					onSelectionChange={(keys) => {
						const [key] = [...keys];
						onChange(key == null ? null : String(key));
					}}
				>
					{(item) => (
						<ListBoxItem id={getId(item)} textValue={getLabel(item)}>
							{getLabel(item)}
						</ListBoxItem>
					)}
				</ListBox>
			</Autocomplete>
		</div>
	);
}
