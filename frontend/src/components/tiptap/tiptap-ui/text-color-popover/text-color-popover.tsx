import type { Editor } from "@tiptap/react";
import { forwardRef, useCallback, useEffect, useState } from "react";
import { HexColorInput, HexColorPicker } from "react-colorful";
// --- Icons ---
import { BanIcon } from "#/components/tiptap/tiptap-icons/ban-icon";
import { CaseSensitiveIcon } from "#/components/tiptap/tiptap-icons/case-sensitive-icon";
// --- Tiptap UI ---
import type { UseTextColorConfig } from "#/components/tiptap/tiptap-ui/text-color-button";
import { useTextColor } from "#/components/tiptap/tiptap-ui/text-color-button";
// --- UI Primitives ---
import type { ButtonProps } from "#/components/tiptap/tiptap-ui-primitive/button";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import { ButtonGroup } from "#/components/tiptap/tiptap-ui-primitive/button-group";
import {
	Card,
	CardBody,
	CardItemGroup,
} from "#/components/tiptap/tiptap-ui-primitive/card";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "#/components/tiptap/tiptap-ui-primitive/popover";
import { useIsBreakpoint } from "#/hooks/use-is-breakpoint";
// --- Hooks ---
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

import "#/components/tiptap/tiptap-ui/text-color-popover/text-color-popover.scss";

const DEFAULT_TEXT_COLOR = "#000000";

export interface TextColorPopoverContentProps {
	/**
	 * The Tiptap editor instance.
	 */
	editor?: Editor | null;
}

export interface TextColorPopoverProps
	extends Omit<ButtonProps, "type">,
		Pick<UseTextColorConfig, "editor" | "hideWhenUnavailable" | "onApplied"> {}

export const TextColorPopoverButton = forwardRef<HTMLButtonElement, ButtonProps>(
	({ className, children, ...props }, ref) => (
		<Button
			type="button"
			className={className}
			variant="ghost"
			data-appearance="default"
			role="button"
			tabIndex={-1}
			aria-label="Text color"
			tooltip="Text color"
			ref={ref}
			{...props}
		>
			{children ?? <CaseSensitiveIcon className="tiptap-button-icon" />}
		</Button>
	),
);

TextColorPopoverButton.displayName = "TextColorPopoverButton";

export function TextColorPopoverContent({
	editor: providedEditor,
}: TextColorPopoverContentProps) {
	const { editor } = useTiptapEditor(providedEditor);
	const isMobile = useIsBreakpoint();
	const activeColor = editor?.getAttributes("textStyle").color as string | undefined;
	const [color, setColor] = useState(activeColor || DEFAULT_TEXT_COLOR);

	useEffect(() => {
		setColor(activeColor || DEFAULT_TEXT_COLOR);
	}, [activeColor]);

	const applyColor = useCallback(
		(value: string) => {
			setColor(value);
			// Don't call `.focus()` here: it would move DOM focus into the
			// editor, which sits outside the popover in the DOM tree, causing
			// Radix to treat it as an outside interaction and close the
			// popover mid-drag. The transaction still applies without focus;
			// focus is restored when the popover closes.
			editor?.chain().setColor(value).run();
		},
		[editor],
	);

	const handleRemoveTextColor = useCallback(() => {
		editor?.chain().unsetColor().run();
	}, [editor]);

	return (
		<Card tabIndex={0} style={isMobile ? { boxShadow: "none", border: 0 } : {}}>
			<CardBody style={isMobile ? { padding: 0 } : {}}>
				<CardItemGroup orientation="vertical">
					<HexColorPicker
						className="tiptap-text-color-picker"
						color={color}
						onChange={applyColor}
					/>
					<CardItemGroup orientation="horizontal">
						<HexColorInput
							className="tiptap-input tiptap-text-color-hex-input"
							color={color}
							onChange={applyColor}
							prefixed
							autoFocus
						/>
						<ButtonGroup>
							<Button
								onClick={handleRemoveTextColor}
								aria-label="Remove text color"
								tooltip="Remove text color"
								type="button"
								variant="ghost"
							>
								<BanIcon className="tiptap-button-icon" />
							</Button>
						</ButtonGroup>
					</CardItemGroup>
				</CardItemGroup>
			</CardBody>
		</Card>
	);
}

export function TextColorPopover({
	editor: providedEditor,
	hideWhenUnavailable = false,
	onApplied,
	...props
}: TextColorPopoverProps) {
	const { editor } = useTiptapEditor(providedEditor);
	const [isOpen, setIsOpen] = useState(false);
	const { isVisible, canSetTextColor, isActive, label, Icon } = useTextColor({
		editor,
		hideWhenUnavailable,
		onApplied,
	});

	if (!isVisible) return null;

	return (
		<Popover open={isOpen} onOpenChange={setIsOpen}>
			<PopoverTrigger asChild>
				<TextColorPopoverButton
					disabled={!canSetTextColor}
					data-active-state={isActive ? "on" : "off"}
					data-disabled={!canSetTextColor}
					aria-pressed={isActive}
					aria-label={label}
					tooltip={label}
					{...props}
				>
					<Icon className="tiptap-button-icon" />
				</TextColorPopoverButton>
			</PopoverTrigger>
			<PopoverContent
				aria-label="Text colors"
				onCloseAutoFocus={(event) => {
					// Radix returns focus to the trigger button by default when the
					// popover closes. Keep focus in the editor instead, matching the
					// link popover's behavior. Also collapse the selection to its
					// end (rather than restoring the pre-existing range) so the
					// cursor lands after the colored text instead of before it.
					event.preventDefault();
					if (!editor) return;
					const { to } = editor.state.selection;
					editor.chain().focus().setTextSelection(to).run();
				}}
			>
				<TextColorPopoverContent editor={editor} />
			</PopoverContent>
		</Popover>
	);
}

export default TextColorPopover;
