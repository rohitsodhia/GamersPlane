import clsx from "clsx";
import type { CSSProperties, ReactNode } from "react";
import { ListModeProvider } from "./loop-context";
import type { ListMarker } from "./types";

interface ListProps {
	variant: "ordered" | "unordered";
	marker?: ListMarker;
	className?: string;
	style?: CSSProperties;
	children?: ReactNode;
}

/**
 * An `<ol>` / `<ul>` wrapper (see `ListElement`). `variant` picks the tag;
 * `marker` overrides `list-style-type` from the bounded `ListMarker` set.
 * Provides `ListModeProvider` so a `loop` inside emits one `<li>` per iteration.
 */
export function List({ variant, marker, className, style, children }: ListProps) {
	const Tag = variant === "ordered" ? "ol" : "ul";
	const listStyle: CSSProperties | undefined = marker
		? { ...style, listStyleType: marker }
		: style;
	return (
		<ListModeProvider>
			<Tag className={clsx("char-sheet-list", className)} style={listStyle}>
				{children}
			</Tag>
		</ListModeProvider>
	);
}
