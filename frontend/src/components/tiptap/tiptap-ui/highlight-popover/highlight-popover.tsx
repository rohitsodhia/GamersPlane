import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import { useState } from "react";
import { HIGHLIGHT_PALETTE } from "#/components/tiptap/tiptap-extension/color-palette";
import { BanIcon } from "#/components/tiptap/tiptap-icons/ban-icon";
import { HighlighterIcon } from "#/components/tiptap/tiptap-icons/highlighter-icon";
import { ColorSwatches } from "#/components/tiptap/tiptap-ui/color-swatches/color-swatches";
import { restoreEditorFocus } from "#/components/tiptap/tiptap-ui/color-swatches/restore-editor-focus";
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
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

/**
 * Background (highlight) color: a palette of named colors plus a clear button. The
 * stored value is the hex the swatch carries, so the document never holds anything
 * the palette (or a pasted `data-color`, validated on parse) didn't.
 */
export function HighlightPopover({
	editor: providedEditor,
}: {
	editor?: Editor | null;
}) {
	const { editor } = useTiptapEditor(providedEditor);
	const [isOpen, setIsOpen] = useState(false);
	const activeColor = useEditorState({
		editor,
		selector: ({ editor }) =>
			editor?.isActive("highlight")
				? ((editor.getAttributes("highlight")["color"] as string | undefined) ?? null)
				: null,
	});

	if (!editor) return null;

	return (
		<Popover open={isOpen} onOpenChange={setIsOpen}>
			<PopoverTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label="Highlight color"
					tooltip="Highlight color"
					aria-pressed={editor.isActive("highlight")}
					data-active-state={editor.isActive("highlight") ? "on" : "off"}
				>
					<HighlighterIcon className="tiptap-button-icon" />
				</Button>
			</PopoverTrigger>
			<PopoverContent
				aria-label="Highlight colors"
				onCloseAutoFocus={(event) => {
					// Keep focus in the editor, with the cursor after the highlighted
					// text, same as the text color popover.
					event.preventDefault();
					restoreEditorFocus(editor);
				}}
			>
				<Card tabIndex={0}>
					<CardBody>
						<CardItemGroup orientation="vertical">
							<ColorSwatches
								colors={HIGHLIGHT_PALETTE}
								activeColor={activeColor}
								onPick={(color) => {
									editor.chain().setHighlight({ color }).run();
									setIsOpen(false);
								}}
							/>
							<Button
								type="button"
								variant="ghost"
								aria-label="Remove highlight"
								tooltip="Remove highlight"
								onClick={() => {
									editor.chain().unsetHighlight().run();
									setIsOpen(false);
								}}
							>
								<BanIcon className="tiptap-button-icon" />
								<span className="tiptap-button-text">Remove highlight</span>
							</Button>
						</CardItemGroup>
					</CardBody>
				</Card>
			</PopoverContent>
		</Popover>
	);
}
