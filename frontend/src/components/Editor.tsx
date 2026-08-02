import type { JSONContent } from "@tiptap/core";
import { EditorContent, EditorContext, useEditor } from "@tiptap/react";
import { BubbleMenu, FloatingMenu } from "@tiptap/react/menus";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useMemo } from "react";

export const emptyContent: JSONContent = { type: "doc", content: [] };

export function isContentEmpty(content: JSONContent | null | undefined): boolean {
	if (!content) return true;
	if (content.text) return false;
	return (content.content ?? []).every(isContentEmpty);
}

type EditorProps = {
	id?: string;
	value: JSONContent | null | undefined;
	onChange: (value: JSONContent) => void;
	onBlur?: () => void;
	className?: string;
};

const Editor = ({ id, value, onChange, onBlur, className }: EditorProps) => {
	const editor = useEditor({
		extensions: [StarterKit], // define your extension array
		content: value ?? emptyContent,
		onUpdate: ({ editor }) => {
			onChange(editor.getJSON());
		},
		onBlur: () => {
			onBlur?.();
		},
		editorProps: {
			attributes: id ? { id } : {},
		},
	});

	// Keep the editor in sync when the external value changes without going
	// through onUpdate (e.g. form reset), without clobbering in-progress typing.
	useEffect(() => {
		if (!editor) return;
		const current = JSON.stringify(editor.getJSON());
		const next = JSON.stringify(value ?? emptyContent);
		if (current !== next) {
			editor.commands.setContent(value ?? emptyContent);
		}
	}, [editor, value]);

	// Memoize the provider value to avoid unnecessary re-renders
	const providerValue = useMemo(() => ({ editor }), [editor]);

	return (
		<EditorContext.Provider value={providerValue}>
			<EditorContent editor={editor} className={className} />
			<FloatingMenu editor={editor}>This is the floating menu</FloatingMenu>
			<BubbleMenu editor={editor}>This is the bubble menu</BubbleMenu>
		</EditorContext.Provider>
	);
};

export default Editor;
