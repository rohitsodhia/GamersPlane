import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import { Input, NumberField } from "react-aria-components";
import { Select } from "#/components/Select";
import {
	ORDERED_LIST_TYPES,
	safeListStart,
	safeListType,
} from "#/components/tiptap/tiptap-extension/ordered-list-extension";
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

import "#/components/tiptap/tiptap-ui/ordered-list-options/ordered-list-options.scss";

/**
 * The start number and numbering style of the ordered list the caret is in. Renders
 * nothing outside an ordered list.
 */
export function OrderedListOptions({
	editor: providedEditor,
}: {
	editor?: Editor | null;
}) {
	const { editor } = useTiptapEditor(providedEditor);
	const list = useEditorState({
		editor,
		selector: ({ editor }) =>
			editor?.isActive("orderedList")
				? {
						start: safeListStart(editor.getAttributes("orderedList")["start"]),
						type: safeListType(editor.getAttributes("orderedList")["type"]) ?? "1",
					}
				: null,
	});

	if (!editor || !list) return null;

	return (
		<div className="tiptap-ordered-list-options">
			<NumberField
				aria-label="List starts at"
				name="list_start"
				value={list.start}
				minValue={1}
				step={1}
				onChange={(start) => {
					// Cleared or non-numeric input reports NaN; wait for a real number.
					if (!Number.isInteger(start) || start < 1) return;
					editor.chain().updateAttributes("orderedList", { start }).run();
				}}
			>
				<Input className="tiptap-input" />
			</NumberField>
			<Select
				id="tiptap-ordered-list-type"
				name="list_numbering"
				ariaLabel="List numbering"
				items={[...ORDERED_LIST_TYPES]}
				getId={(item) => item.key}
				getLabel={(item) => item.label}
				selectedId={list.type}
				onChange={(key) => {
					const type = safeListType(key);
					if (!type) return;
					editor
						.chain()
						.updateAttributes("orderedList", { type: type === "1" ? null : type })
						.run();
				}}
			/>
		</div>
	);
}
