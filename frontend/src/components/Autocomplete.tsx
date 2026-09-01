import { useState } from "react";
import { useFilter } from "react-aria";
import {
	Input,
	Menu,
	MenuItem,
	Autocomplete as RACAutocomplete,
	SearchField,
} from "react-aria-components";

export function Autocomplete<T>({
	id,
	items,
	getId,
	getLabel,
	onAction,
	onInputChange,
	inputValue: controlledValue,
}: {
	id: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	onAction: (id: string) => void;
	onInputChange?: (value: string) => void;
	// When supplied, the caller drives the input value (and must keep it in sync
	// via onInputChange). Left undefined, the input stays uncontrolled.
	inputValue?: string;
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

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: closes the menu when focus leaves it
		<div
			onBlur={(e) => {
				if (!e.currentTarget.contains(e.relatedTarget)) setIsOpen(false);
			}}
		>
			<RACAutocomplete
				filter={isAsync ? undefined : contains}
				inputValue={controlledValue}
				onInputChange={(value) => {
					setUncontrolledValue(value);
					onInputChange?.(value);
				}}
			>
				<SearchField id={id} onFocus={() => setIsOpen(true)}>
					<Input onKeyDown={() => setIsOpen(true)} />
				</SearchField>
				{isOpen && hasItems && (
					<Menu
						items={items}
						onAction={(key) => {
							onAction(key as string);
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
