import { useRef } from "react";

/**
 * Makes a `DialogTrigger`'s trigger toggle a non-modal popover: one press opens,
 * the next closes. Without it the second press closes and reopens: a non-modal
 * RAC popover closes itself on blur, so pressing the trigger closes it (focus
 * leaves the dialog) and the press then toggles it straight back open. This
 * remembers the popover was open when the press began and swallows that reopen.
 *
 * Pass `onOpenChange` to the `DialogTrigger` and `onPressStart` to its `Button`.
 */
export function usePopoverToggle(isOpen: boolean, setOpen: (open: boolean) => void) {
	const wasOpenAtPress = useRef(false);
	return {
		onOpenChange: (next: boolean) => {
			if (next && wasOpenAtPress.current) {
				wasOpenAtPress.current = false;
				return;
			}
			setOpen(next);
		},
		onPressStart: () => {
			wasOpenAtPress.current = isOpen;
		},
	};
}
