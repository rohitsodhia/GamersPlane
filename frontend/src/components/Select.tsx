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
}: {
	id: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	selectedId: string;
	onChange: (id: string) => void;
}) {
	return (
		<RACSelect
			selectedKey={selectedId}
			onSelectionChange={(key) => onChange(key as string)}
		>
			<Button id={id}>
				<SelectValue />
				<span aria-hidden="true">▼</span>
			</Button>
			<Popover>
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
