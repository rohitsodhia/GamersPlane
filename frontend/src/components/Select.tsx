import {
	Button,
	ListBox,
	ListBoxItem,
	Popover,
	Select as RACSelect,
	SelectValue,
} from "react-aria-components";

export function Select<T>({
	id,
	items,
	getId,
	getLabel,
	selectedId,
	onChange,
	isDisabled,
}: {
	id: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	selectedId: string;
	onChange: (id: string) => void;
	isDisabled?: boolean;
}) {
	return (
		<RACSelect
			selectedKey={selectedId}
			isDisabled={isDisabled}
			onSelectionChange={(key) => onChange(key as string)}
		>
			<Button id={id}>
				<SelectValue />
				<span aria-hidden="true">▼</span>
			</Button>
			<Popover className="react-aria-Popover react-aria-Select-Popover">
				<ListBox items={items}>
					{(item) => (
						<ListBoxItem id={getId(item)} textValue={getLabel(item)}>
							{getLabel(item)}
						</ListBoxItem>
					)}
				</ListBox>
			</Popover>
		</RACSelect>
	);
}
