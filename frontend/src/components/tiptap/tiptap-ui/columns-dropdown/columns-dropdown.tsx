import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import { ChevronDownIcon } from "#/components/tiptap/tiptap-icons/chevron-down-icon";
import {
	COLUMN_COUNTS,
	COLUMNS_NODE_NAME,
	isColumnCount,
} from "#/components/tiptap/tiptap-node/columns-node/columns-node-extension";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "#/components/tiptap/tiptap-ui-primitive/dropdown-menu";
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

import "#/components/tiptap/tiptap-ui/preset-dropdown/preset-dropdown.scss";

/**
 * Inserts two or three columns. With the caret in columns, the same choices change
 * how many there are (the current count is checked; fewer columns fold the removed
 * ones' content into the last), and the menu adds "Remove columns".
 */
export function ColumnsDropdown({
	editor: providedEditor,
}: {
	editor?: Editor | null;
}) {
	const { editor } = useTiptapEditor(providedEditor);
	const state = useEditorState({
		editor,
		selector: ({ editor }) => {
			// The button renders whenever the editor exists; this state can still be
			// empty on the first render, which is why it is not used to hide it.
			if (!editor) return { inColumns: false, count: "" };
			const inColumns = editor.isActive(COLUMNS_NODE_NAME);
			const count: unknown = editor.getAttributes(COLUMNS_NODE_NAME)["count"];
			return {
				inColumns,
				count: inColumns && isColumnCount(count) ? String(count) : "",
			};
		},
	});

	if (!editor) return null;
	const inColumns = state?.inColumns ?? false;

	return (
		<DropdownMenu modal={false}>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label="Columns"
					tooltip="Columns"
					data-active-state={inColumns ? "on" : "off"}
				>
					<span className="tiptap-preset-dropdown-text">Columns</span>
					<ChevronDownIcon className="tiptap-button-dropdown-small" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" aria-label="Columns">
				<DropdownMenuGroup>
					<DropdownMenuRadioGroup
						value={state?.count ?? ""}
						onValueChange={(value) => {
							const count = Number(value);
							if (isColumnCount(count)) editor.chain().focus().setColumns(count).run();
						}}
					>
						{COLUMN_COUNTS.map((count) => (
							<DropdownMenuRadioItem key={count} value={String(count)}>
								{count} columns
							</DropdownMenuRadioItem>
						))}
					</DropdownMenuRadioGroup>
				</DropdownMenuGroup>
				{inColumns && (
					<>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							className="tiptap-dropdown-menu-radio-item"
							onSelect={() => editor.chain().focus().unsetColumns().run()}
						>
							Remove columns
						</DropdownMenuItem>
					</>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
