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
	autoWidth,
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
	/**
	 * Size the trigger to the widest option label (like a native `<select>`)
	 * instead of the fixed `--rac-field-width`. Renders a hidden sizer that
	 * mirrors the trigger's box for every option.
	 */
	autoWidth?: boolean;
	/** Extra classes on the RAC Select wrapper (the RAC default class is kept). */
	className?: string;
	style?: CSSProperties;
}) {
	return (
		<RACSelect
			className={clsx(
				"react-aria-Select",
				autoWidth && "react-aria-Select--auto-width",
				className,
			)}
			style={style}
			selectedKey={selectedId}
			isDisabled={isDisabled}
			onSelectionChange={(key) => onChange(key as string)}
		>
			<Button id={id} aria-labelledby={ariaLabelledBy}>
				<SelectValue />
				<span aria-hidden="true">▼</span>
			</Button>
			{autoWidth && (
				<span className="react-aria-Select-sizer" aria-hidden="true">
					{items.map((item) => (
						<span key={getId(item)} className="react-aria-Select-sizer-row">
							<span>{getLabel(item)}</span>
							<span>▼</span>
						</span>
					))}
				</span>
			)}
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
