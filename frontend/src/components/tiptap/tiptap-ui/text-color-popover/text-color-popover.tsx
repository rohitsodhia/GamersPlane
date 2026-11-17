import type { Editor } from "@tiptap/react";
import { forwardRef, useState } from "react";
import { HexColorPicker } from "react-colorful";
import { TEXT_PALETTE } from "#/components/tiptap/tiptap-extension/color-palette";
// --- Icons ---
import { BanIcon } from "#/components/tiptap/tiptap-icons/ban-icon";
import { CaseSensitiveIcon } from "#/components/tiptap/tiptap-icons/case-sensitive-icon";
import { CheckIcon } from "#/components/tiptap/tiptap-icons/check-icon";
// --- Tiptap UI ---
import { ColorSwatches } from "#/components/tiptap/tiptap-ui/color-swatches/color-swatches";
import { restoreEditorFocus } from "#/components/tiptap/tiptap-ui/color-swatches/restore-editor-focus";
import type { UseTextColorConfig } from "#/components/tiptap/tiptap-ui/text-color-button";
import { useTextColor } from "#/components/tiptap/tiptap-ui/text-color-button";
// --- UI Primitives ---
import type { ButtonProps } from "#/components/tiptap/tiptap-ui-primitive/button";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
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
	/**
	 * Called after a color is applied or removed: closes the popover, or goes back
	 * to the main toolbar on mobile.
	 */
	onDone?: () => void;
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

const HEX_6 = /^#?[0-9a-f]{6}$/i;

/** `abc123` or `#ABC123` as `#abc123`, or null when it isn't a full 6-digit hex. */
function normalizeHex(value: string): string | null {
	const trimmed = value.trim();
	return HEX_6.test(trimmed) ? `#${trimmed.replace("#", "").toLowerCase()}` : null;
}

/**
 * Swatches apply and close at once. The picker and hex input only edit a local
 * draft, applied by the Apply button (or Enter in the hex field), so nothing
 * reaches the document while dragging or typing. `onDone` closes the popover, or
 * returns to the main toolbar on mobile.
 */
export function TextColorPopoverContent({
	editor: providedEditor,
	onDone,
}: TextColorPopoverContentProps) {
	const { editor } = useTiptapEditor(providedEditor);
	const isMobile = useIsBreakpoint();
	const activeColor = editor?.getAttributes("textStyle").color as string | undefined;
	// The content mounts fresh each time the popover opens, so the draft starts
	// from the selection's current color.
	const [draft, setDraft] = useState(
		(activeColor && normalizeHex(activeColor)) || DEFAULT_TEXT_COLOR,
	);
	const [hexText, setHexText] = useState(draft);
	const hexToApply = normalizeHex(hexText);

	// No `.focus()` here: the editor sits outside the popover in the DOM tree, so
	// moving focus into it would count as an outside interaction and close the
	// popover. The transaction applies without focus, and focus is restored when
	// the popover closes. Stored marks survive because nothing here changes the
	// selection.
	const applyColor = (value: string) => {
		editor?.chain().setColor(value).run();
		onDone?.();
	};

	const handleRemoveTextColor = () => {
		editor?.chain().unsetColor().run();
		onDone?.();
	};

	const handleConfirm = () => {
		if (hexToApply) applyColor(hexToApply);
	};

	return (
		<Card tabIndex={0} style={isMobile ? { boxShadow: "none", border: 0 } : {}}>
			<CardBody
				className={
					isMobile
						? "tiptap-text-color-body tiptap-text-color-body-mobile"
						: "tiptap-text-color-body"
				}
			>
				<CardItemGroup orientation="vertical" className="tiptap-text-color-group">
					<ColorSwatches
						colors={TEXT_PALETTE}
						activeColor={activeColor}
						onPick={applyColor}
					/>
					<HexColorPicker
						className="tiptap-text-color-picker"
						color={draft}
						onChange={(value) => {
							setDraft(value);
							setHexText(value);
						}}
					/>
					<div className="tiptap-text-color-hex-row">
						<input
							className="tiptap-input tiptap-text-color-hex-input"
							aria-label="Hex color"
							name="hex_color"
							value={hexText}
							spellCheck={false}
							maxLength={7}
							aria-invalid={hexToApply === null}
							onChange={(event) => {
								const text = event.target.value;
								setHexText(text);
								const valid = normalizeHex(text);
								if (valid) setDraft(valid);
							}}
							onKeyDown={(event) => {
								if (event.key !== "Enter") return;
								event.preventDefault();
								handleConfirm();
							}}
						/>
						<Button
							type="button"
							variant="primary"
							aria-label="Apply color"
							tooltip="Apply color"
							disabled={hexToApply === null}
							onClick={handleConfirm}
						>
							<CheckIcon className="tiptap-button-icon" />
							<span className="tiptap-button-text">Apply</span>
						</Button>
						<Button
							onClick={handleRemoveTextColor}
							aria-label="Remove text color"
							tooltip="Remove text color"
							type="button"
							variant="ghost"
						>
							<BanIcon className="tiptap-button-icon" />
						</Button>
					</div>
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
					restoreEditorFocus(editor);
				}}
			>
				<TextColorPopoverContent editor={editor} onDone={() => setIsOpen(false)} />
			</PopoverContent>
		</Popover>
	);
}

export default TextColorPopover;
