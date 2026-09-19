import clsx from "clsx";
import type { CSSProperties, ReactNode } from "react";
import { useCollapsible } from "./collapsible-scope";

interface CollapsibleProps {
	name: string;
	collapsed?: boolean;
	className?: string;
	style?: CSSProperties;
	children?: ReactNode;
}

/**
 * A region that shows/hides in response to a sibling `collapsible-toggle` with
 * a matching `target`. It renders no trigger of its own — the control has to sit
 * outside the region so it stays visible when the region is closed.
 *
 * The open flag lives in the nearest disclosure scope (sheet root, or one per
 * repeater / grid row), keyed by `name`; `collapsed` sets the initial state.
 * Closed = the body collapsed to zero height (a CSS grid-rows transition) and
 * `inert`, so its fields leave the tab order.
 */
export function Collapsible({
	name,
	collapsed = false,
	className,
	style,
	children,
}: CollapsibleProps) {
	const { open, bodyId } = useCollapsible(name, collapsed);

	if (import.meta.env.DEV && !name) {
		console.warn("[sheet] collapsible has no `name`; nothing can toggle it");
	}

	return (
		<div
			className={clsx("char-sheet-collapsible", className)}
			style={style}
			data-open={open}
		>
			<div id={bodyId} className="char-sheet-collapsible-body" inert={!open}>
				<div className="char-sheet-collapsible-body-inner">{children}</div>
			</div>
		</div>
	);
}
