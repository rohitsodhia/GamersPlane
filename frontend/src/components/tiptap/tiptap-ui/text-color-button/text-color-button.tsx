"use client";
"use no memo";

import { forwardRef, useCallback, useMemo } from "react";
// --- Tiptap UI ---
import type { UseTextColorConfig } from "#/components/tiptap/tiptap-ui/text-color-button";
import {
	TEXT_COLOR_SHORTCUT_KEY,
	useTextColor,
} from "#/components/tiptap/tiptap-ui/text-color-button";
import { Badge } from "#/components/tiptap/tiptap-ui-primitive/badge";
// --- UI Primitives ---
import type { ButtonProps } from "#/components/tiptap/tiptap-ui-primitive/button";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
// --- Hooks ---
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";
// --- Lib ---
import { parseShortcutKeys } from "#/lib/tiptap-utils";

// --- Styles ---
import "#/components/tiptap/tiptap-ui/text-color-button/text-color-button.scss";

export interface TextColorButtonProps
	extends Omit<ButtonProps, "type">,
		UseTextColorConfig {
	/**
	 * Optional text to display alongside the icon.
	 */
	text?: string;
	/**
	 * Optional show shortcut keys in the button.
	 * @default false
	 */
	showShortcut?: boolean;
}

export function TextColorShortcutBadge({
	shortcutKeys = TEXT_COLOR_SHORTCUT_KEY,
}: {
	shortcutKeys?: string;
}) {
	return <Badge>{parseShortcutKeys({ shortcutKeys })}</Badge>;
}

/**
 * Button component for applying text colors in a Tiptap editor.
 *
 * For custom button implementations, use the `useTextColor` hook instead.
 */
export const TextColorButton = forwardRef<HTMLButtonElement, TextColorButtonProps>(
	(
		{
			editor: providedEditor,
			textColor,
			text,
			hideWhenUnavailable = false,
			onApplied,
			showShortcut = false,
			onClick,
			children,
			style,
			...buttonProps
		},
		ref,
	) => {
		const { editor } = useTiptapEditor(providedEditor);
		const {
			isVisible,
			canSetTextColor,
			isActive,
			handleSetTextColor,
			label,
			shortcutKeys,
		} = useTextColor({
			editor,
			textColor,
			label: text || `Text color (${textColor})`,
			hideWhenUnavailable,
			onApplied,
		});

		const handleClick = useCallback(
			(event: React.MouseEvent<HTMLButtonElement>) => {
				onClick?.(event);
				if (event.defaultPrevented) return;
				handleSetTextColor();
			},
			[handleSetTextColor, onClick],
		);

		const buttonStyle = useMemo(
			() =>
				({
					...style,
					"--text-color": textColor,
				}) as React.CSSProperties,
			[textColor, style],
		);

		if (!isVisible) {
			return null;
		}

		return (
			<Button
				type="button"
				variant="ghost"
				data-active-state={isActive ? "on" : "off"}
				role="button"
				tabIndex={-1}
				disabled={!canSetTextColor}
				data-disabled={!canSetTextColor}
				aria-label={label}
				aria-pressed={isActive}
				tooltip={label}
				onClick={handleClick}
				style={buttonStyle}
				{...buttonProps}
				ref={ref}
			>
				{children ?? (
					<>
						<span
							className="tiptap-button-text-color"
							style={{ "--text-color": textColor } as React.CSSProperties}
						/>
						{text && <span className="tiptap-button-text">{text}</span>}
						{showShortcut && <TextColorShortcutBadge shortcutKeys={shortcutKeys} />}
					</>
				)}
			</Button>
		);
	},
);

TextColorButton.displayName = "TextColorButton";
