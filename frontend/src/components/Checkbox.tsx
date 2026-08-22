import { Checkbox as RACCheckbox } from "react-aria-components";

export function Checkbox({
	id,
	checked,
	onChange,
}: {
	id: string;
	checked: boolean;
	onChange: (checked: boolean) => void;
}) {
	return (
		<RACCheckbox id={id} isSelected={checked} onChange={onChange}>
			<div className="checkbox-box">
				<svg viewBox="0 0 18 18" aria-hidden="true">
					<polyline points="1 9 7 14 15 4" />
				</svg>
			</div>
		</RACCheckbox>
	);
}
