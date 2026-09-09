import clsx from "clsx";
import type { CSSProperties } from "react";
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
	className,
	style,
	ariaLabelledBy,
}: {
	id: string;
	items: T[];
	getId: (item: T) => string;
	getLabel: (item: T) => string;
	selectedId: string;
	onChange: (id: string) => void;
	isDisabled?: boolean;
	/** Forwarded to the trigger button's `aria-labelledby`. */
	ariaLabelledBy?: string;
	/** Extra classes on the RAC Select wrapper (the RAC default class is kept). */
	className?: string;
	style?: CSSProperties;
}) {
	return (
		<RACSelect
			className={clsx("react-aria-Select", className)}
			style={style}
			selectedKey={selectedId}
			isDisabled={isDisabled}
			onSelectionChange={(key) => onChange(key as string)}
		>
			<Button id={id} aria-labelledby={ariaLabelledBy}>
				<SelectValue />
				<span aria-hidden="true">▼</span>
			</Button>
			{/* Hidden sizer: mirrors the trigger's box for every option so the trigger
			    column grows to fit the widest label (native `<select>` behaviour).
			    A consumer that sets `--rac-select-width` in its own stylesheet opts
			    back into a fixed width. */}
			<span className="react-aria-Select-sizer" aria-hidden="true">
				{items.map((item) => (
					<span key={getId(item)} className="react-aria-Select-sizer-row">
						<span>{getLabel(item)}</span>
						<span>▼</span>
					</span>
				))}
			</span>
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
