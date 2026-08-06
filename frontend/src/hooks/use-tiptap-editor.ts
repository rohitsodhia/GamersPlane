"use no memo";

import type { Editor } from "@tiptap/react";
import { useCurrentEditor, useEditorState } from "@tiptap/react";
import { useEffect, useState } from "react";

function getActivePageEditor(editor: Editor): Editor | null {
	const storage = editor.storage as unknown as Record<string, unknown>;
	const pages = storage.pages as { activeEditor?: Editor | null } | undefined;
	if (!pages || !("activeEditor" in pages)) return null;
	return pages.activeEditor ?? null;
}

export function useTiptapEditor(providedEditor?: Editor | null): {
	editor: Editor | null;
	editorState?: Editor["state"];
	canCommand?: Editor["can"];
} {
	const { editor: coreEditor } = useCurrentEditor();
	const mainEditor = providedEditor ?? coreEditor;

	const [storageEditor, setStorageEditor] = useState<Editor | null>(null);

	useEffect(() => {
		if (!mainEditor) {
			setStorageEditor(null);
			return;
		}

		const updateHandler = () => setStorageEditor(getActivePageEditor(mainEditor));

		updateHandler();

		mainEditor.on("update", updateHandler);
		mainEditor.on("selectionUpdate", updateHandler);

		return () => {
			mainEditor.off("update", updateHandler);
			mainEditor.off("selectionUpdate", updateHandler);
		};
	}, [mainEditor]);

	useEffect(() => {
		if (!storageEditor) return;

		const handleDestroy = () => setStorageEditor(null);

		storageEditor.on("destroy", handleDestroy);
		return () => {
			storageEditor.off("destroy", handleDestroy);
		};
	}, [storageEditor]);

	const editorState = useEditorState({
		editor: storageEditor ?? mainEditor,
		selector(context) {
			if (!context.editor) {
				return { editor: null, editorState: undefined, canCommand: undefined };
			}

			return {
				editor: context.editor,
				editorState: context.editor.state,
				canCommand: context.editor.can,
			};
		},
		// editor.state is a new object on every transaction (ProseMirror state is
		// immutable) and editor.can is a bound method — deep-equality (the
		// default) walks the whole ProseMirror doc/schema graph on every check,
		// which is both slow and unreliable on a graph with internal shared
		// structure, causing stale reads (e.g. toolbar buttons not updating
		// enabled/active state after a selection change). Reference equality on
		// each field is cheap and correct here since state is never mutated in place.
		equalityFn: (a, b) =>
			a?.editor === b?.editor &&
			a?.editorState === b?.editorState &&
			a?.canCommand === b?.canCommand,
	});

	return editorState ?? { editor: null };
}
