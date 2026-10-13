import { useLocation } from "@tanstack/react-router";
import clsx from "clsx";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import { usePopoverToggle } from "#/lib/use-popover-toggle";
import styles from "./GameBar.module.css";

// A game-bar item that opens a popover sitting on the bar: the trigger fills the
// bar's height like its links, and a second press on it closes the popover.
// Non-modal so opening it doesn't lock page scrolling (see `ActionsMenu`), which
// means an outside press and Escape close it by hand. `children` gets a `close`
// for content that should dismiss it (picking a character). Navigating closes it.
export default function BarPopover({
	label,
	placement,
	dialogClassName,
	children,
}: {
	label: string;
	placement: "top start" | "top end";
	dialogClassName?: string;
	children: ReactNode | ((close: () => void) => ReactNode);
}) {
	const [open, setOpen] = useState(false);
	const triggerRef = useRef<HTMLButtonElement>(null);

	// Any navigation closes it (the bar stays mounted across game pages).
	const href = useLocation({ select: (location) => location.href });
	const [shownAt, setShownAt] = useState(href);
	if (href !== shownAt) {
		setShownAt(href);
		setOpen(false);
	}
	const popoverRef = useRef<HTMLElement>(null);

	useEffect(() => {
		if (!open) return;
		const closeOnOutsidePress = (e: PointerEvent) => {
			const target = e.target as Node;
			if (popoverRef.current?.contains(target)) return;
			if (triggerRef.current?.contains(target)) return;
			setOpen(false);
		};
		const closeOnEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape") setOpen(false);
		};
		document.addEventListener("pointerdown", closeOnOutsidePress);
		document.addEventListener("keydown", closeOnEscape);
		return () => {
			document.removeEventListener("pointerdown", closeOnOutsidePress);
			document.removeEventListener("keydown", closeOnEscape);
		};
	}, [open]);

	const toggle = usePopoverToggle(open, setOpen);

	return (
		<DialogTrigger isOpen={open} onOpenChange={toggle.onOpenChange}>
			<Button
				ref={triggerRef}
				className={styles["item"]}
				onPressStart={toggle.onPressStart}
			>
				{label}
			</Button>
			<Popover
				ref={popoverRef}
				// Keep RAC's default class too: it carries the shared floating-panel surface.
				className={clsx("react-aria-Popover", styles["popover"])}
				placement={placement}
				// The trigger fills the bar's height, so 1px clears the bar's top border
				// and the popover sits on it.
				offset={1}
				isNonModal
			>
				<Dialog className={dialogClassName} aria-label={label}>
					{typeof children === "function" ? children(() => setOpen(false)) : children}
				</Dialog>
			</Popover>
		</DialogTrigger>
	);
}
