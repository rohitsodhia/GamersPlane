import { useEffect, useRef, useState } from "react";
import { Button, Menu, MenuItem, MenuTrigger, Popover } from "react-aria-components";
import styles from "./ActionsMenu.module.css";

export type MenuAction = {
	label: string;
	onAction: () => void;
	disabled?: boolean;
};

// A gear button that opens a dropdown of row actions. Renders nothing when
// there are no actions, so callers can pass a conditionally built list.
export function ActionsMenu({
	label,
	actions,
}: {
	/** Accessible name for the gear button, e.g. "Actions for ratcatcher". */
	label: string;
	actions: MenuAction[];
}) {
	const [isOpen, setIsOpen] = useState(false);
	const popoverRef = useRef<HTMLElement>(null);

	// The popover is non-modal so opening it doesn't lock page scrolling (which
	// hides the scrollbar) — that's reserved for page-blocking overlays. A
	// non-modal popover doesn't close on an outside click, so do that here. That
	// includes the trigger: a mouse press on it only ever *opens* the menu (a
	// no-op when already open), and React's handlers run before this document
	// listener, so pressing the gear again closes the menu.
	useEffect(() => {
		if (!isOpen) return;
		const closeOnOutsidePress = (e: PointerEvent) => {
			if (popoverRef.current?.contains(e.target as Node)) return;
			setIsOpen(false);
		};
		document.addEventListener("pointerdown", closeOnOutsidePress);
		return () => document.removeEventListener("pointerdown", closeOnOutsidePress);
	}, [isOpen]);

	if (actions.length === 0) return null;

	return (
		<MenuTrigger isOpen={isOpen} onOpenChange={setIsOpen}>
			<Button className={styles["trigger"]} aria-label={label}>
				<img src="/images/icons/gear.png" alt="" />
			</Button>
			<Popover ref={popoverRef} placement="bottom end" isNonModal>
				<Menu
					items={actions.map((action) => ({ ...action, id: action.label }))}
					disabledKeys={actions
						.filter((action) => action.disabled)
						.map((action) => action.label)}
					onAction={(key) => actions.find((action) => action.label === key)?.onAction()}
				>
					{(action) => <MenuItem id={action.id}>{action.label}</MenuItem>}
				</Menu>
			</Popover>
		</MenuTrigger>
	);
}
