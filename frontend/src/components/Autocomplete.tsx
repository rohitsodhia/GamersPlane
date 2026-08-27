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
}: {
	id: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	onAction: (id: string) => void;
}) {
	const { contains } = useFilter({ sensitivity: "base" });
	const [isOpen, setIsOpen] = useState(false);

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: closes the menu when focus leaves it
		<div
			onBlur={(e) => {
				if (!e.currentTarget.contains(e.relatedTarget)) setIsOpen(false);
			}}
		>
			<RACAutocomplete filter={contains}>
				<SearchField id={id} onFocus={() => setIsOpen(true)}>
					<Input onKeyDown={() => setIsOpen(true)} />
				</SearchField>
				{isOpen && (
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
