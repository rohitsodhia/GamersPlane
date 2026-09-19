import clsx from "clsx";
import type { CSSProperties, ReactNode } from "react";

interface SectionProps {
	className?: string;
	style?: CSSProperties;
	children?: ReactNode;
}

/**
 * A plain grouping wrapper. Provides visual separation and a styling hook; its
 * children are rendered by the sheet renderer and handed in via `children`.
 */
export function Section({ className, style, children }: SectionProps) {
	return (
		<div className={clsx("char-sheet-section", className)} style={style}>
			{children}
		</div>
	);
}
