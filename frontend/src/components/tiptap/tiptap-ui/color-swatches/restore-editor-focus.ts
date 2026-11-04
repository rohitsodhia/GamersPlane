import type { Editor } from "@tiptap/react";

/**
 * Hand focus back to the editor when a color popover closes. A range selection is
 * collapsed to its end so the cursor lands after the colored text. An empty cursor
 * is left alone and only focused through the view: dispatching any selection
 * transaction there would clear the stored marks, throwing away a color or
 * highlight just picked for the text about to be typed.
 */
export function restoreEditorFocus(editor: Editor | null | undefined) {
	if (!editor) return;
	const { from, to } = editor.state.selection;
	if (from === to) {
		editor.view.focus();
		return;
	}
	editor.chain().focus().setTextSelection(to).run();
}
