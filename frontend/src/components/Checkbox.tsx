import { Checkbox as RACCheckbox } from "react-aria-components";

export function Checkbox({
	id,
	checked,
	onChange,
	disabled,
	className,
}: {
	id: string;
	checked: boolean;
	onChange: (checked: boolean) => void;
	disabled?: boolean;
	className?: string;
}) {
	return (
		<RACCheckbox
			id={id}
			isSelected={checked}
			onChange={onChange}
			isDisabled={disabled}
			// Added to RAC's default class rather than replacing it, which rac.css styles.
			className={className ? `react-aria-Checkbox ${className}` : undefined}
		>
			<div className="checkbox-box">
				<svg viewBox="0 0 18 18" aria-hidden="true">
					<polyline points="1 9 7 14 15 4" />
				</svg>
			</div>
		</RACCheckbox>
	);
}
