"use client";
"use no memo";

import type { Editor } from "@tiptap/react";
import { useCallback, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
// --- Icons ---
import { CaseSensitiveIcon } from "#/components/tiptap/tiptap-icons/case-sensitive-icon";
import { useIsBreakpoint } from "#/hooks/use-is-breakpoint";
// --- Hooks ---
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";
// --- Lib ---
import { isMarkInSchema, isNodeTypeSelected } from "#/lib/tiptap-utils";

export const TEXT_COLOR_SHORTCUT_KEY = "mod+shift+t";

export const TEXT_COLORS = [
	{ label: "Gray", value: "var(--tt-color-text-gray)" },
	{ label: "Brown", value: "var(--tt-color-text-brown)" },
	{ label: "Orange", value: "var(--tt-color-text-orange)" },
	{ label: "Yellow", value: "var(--tt-color-text-yellow)" },
	{ label: "Green", value: "var(--tt-color-text-green)" },
	{ label: "Blue", value: "var(--tt-color-text-blue)" },
	{ label: "Purple", value: "var(--tt-color-text-purple)" },
	{ label: "Pink", value: "var(--tt-color-text-pink)" },
	{ label: "Red", value: "var(--tt-color-text-red)" },
];
export type TextColor = (typeof TEXT_COLORS)[number];

export function pickTextColorsByValue(values: string[]) {
	const colorMap = new Map(TEXT_COLORS.map((color) => [color.value, color]));
	return values
		.map((value) => colorMap.get(value))
		.filter((color): color is (typeof TEXT_COLORS)[number] => !!color);
}

/**
 * Configuration for the text color functionality
 */
export interface UseTextColorConfig {
	/**
	 * The Tiptap editor instance.
	 */
	editor?: Editor | null;
	/**
	 * The color to apply when setting the text color.
	 */
	textColor?: string;
	/**
	 * Optional label to display alongside the icon.
	 */
	label?: string;
	/**
	 * Whether the button should hide when the mark is not available.
	 * @default false
	 */
	hideWhenUnavailable?: boolean;
	/**
	 * Called when the text color is applied.
	 */
	onApplied?: ({ color, label }: { color: string; label: string }) => void;
}

/**
 * Checks if text color can be applied based on the current editor state
 */
export function canSetTextColor(editor: Editor | null): boolean {
	if (!editor || !editor.isEditable) return false;
	if (!isMarkInSchema("textStyle", editor) || isNodeTypeSelected(editor, ["image"]))
		return false;

	return editor.can().setColor("inherit");
}

/**
 * Checks if a text color is currently active
 */
export function isTextColorActive(editor: Editor | null, textColor?: string): boolean {
	if (!editor || !editor.isEditable) return false;

	return textColor
		? editor.isActive("textStyle", { color: textColor })
		: editor.isActive("textStyle");
}

/**
 * Removes the text color
 */
export function removeTextColor(editor: Editor | null): boolean {
	if (!editor || !editor.isEditable) return false;
	if (!canSetTextColor(editor)) return false;

	return editor.chain().focus().unsetColor().run();
}

/**
 * Determines if the text color button should be shown
 */
export function shouldShowButton(props: {
	editor: Editor | null;
	hideWhenUnavailable: boolean;
}): boolean {
	const { editor, hideWhenUnavailable } = props;

	if (!editor) return false;

	if (!hideWhenUnavailable) {
		return true;
	}

	if (!editor.isEditable) return false;

	if (!isMarkInSchema("textStyle", editor)) return false;

	if (!editor.isActive("code")) {
		return canSetTextColor(editor);
	}

	return true;
}

export function useTextColor(config: UseTextColorConfig) {
	const {
		editor: providedEditor,
		label,
		textColor,
		hideWhenUnavailable = false,
		onApplied,
	} = config;

	const { editor } = useTiptapEditor(providedEditor);
	const isMobile = useIsBreakpoint();
	const [isVisible, setIsVisible] = useState<boolean>(true);
	const canSetTextColorState = canSetTextColor(editor);
	const isActive = isTextColorActive(editor, textColor);

	useEffect(() => {
		if (!editor) return;

		const handleSelectionUpdate = () => {
			setIsVisible(shouldShowButton({ editor, hideWhenUnavailable }));
		};

		handleSelectionUpdate();

		editor.on("selectionUpdate", handleSelectionUpdate);

		return () => {
			editor.off("selectionUpdate", handleSelectionUpdate);
		};
	}, [editor, hideWhenUnavailable]);

	const handleSetTextColor = useCallback(() => {
		if (!editor || !canSetTextColorState || !textColor || !label) return false;

		const success = editor.chain().focus().setColor(textColor).run();
		if (success) {
			onApplied?.({ color: textColor, label });
		}
		return success;
	}, [canSetTextColorState, textColor, editor, label, onApplied]);

	const handleRemoveTextColor = useCallback(() => {
		const success = removeTextColor(editor);
		if (success) {
			onApplied?.({ color: "", label: "Remove text color" });
		}
		return success;
	}, [editor, onApplied]);

	useHotkeys(
		TEXT_COLOR_SHORTCUT_KEY,
		(event) => {
			event.preventDefault();
			handleSetTextColor();
		},
		{
			enabled: isVisible && canSetTextColorState,
			enableOnContentEditable: !isMobile,
			enableOnFormTags: true,
		},
	);

	return {
		isVisible,
		isActive,
		handleSetTextColor,
		handleRemoveTextColor,
		canSetTextColor: canSetTextColorState,
		label: label || "Text color",
		shortcutKeys: TEXT_COLOR_SHORTCUT_KEY,
		Icon: CaseSensitiveIcon,
	};
}
