import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import { ChevronDownIcon } from "#/components/tiptap/tiptap-icons/chevron-down-icon";
import {
	isTableAlignKey,
	isTableHeaderKey,
	TABLE_ALIGNS,
	TABLE_FLAGS,
	TABLE_HEADERS,
	TABLE_NODE_NAME,
} from "#/components/tiptap/tiptap-node/table-node/table-node-extension";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "#/components/tiptap/tiptap-ui-primitive/dropdown-menu";
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

import "#/components/tiptap/tiptap-ui/preset-dropdown/preset-dropdown.scss";

/**
 * Inserts a table. With the caret in a table, the menu instead edits it: add or
 * remove rows and columns, change its look (flags, header, and alignment), or delete
 * it.
 */
export function TableDropdown({ editor: providedEditor }: { editor?: Editor | null }) {
	const { editor } = useTiptapEditor(providedEditor);
	const state = useEditorState({
		editor,
		selector: ({ editor }) => {
			// The button renders whenever the editor exists; this state can still be
			// empty on the first render, which is why it is not used to hide it.
			if (!editor) {
				return {
					inTable: false,
					compact: false,
					grid: false,
					zebra: false,
					header: "none",
					align: "left",
				};
			}
			const inTable = editor.isActive(TABLE_NODE_NAME);
			const attrs = editor.getAttributes(TABLE_NODE_NAME);
			return {
				inTable,
				compact: inTable && attrs["compact"] === true,
				grid: inTable && attrs["grid"] === true,
				zebra: inTable && attrs["zebra"] === true,
				header: inTable && isTableHeaderKey(attrs["header"]) ? attrs["header"] : "none",
				align: inTable && isTableAlignKey(attrs["align"]) ? attrs["align"] : "left",
			};
		},
	});

	if (!editor) return null;
	const inTable = state?.inTable ?? false;
	const run = () => editor.chain().focus();

	return (
		<DropdownMenu modal={false}>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label="Table"
					tooltip="Table"
					data-active-state={inTable ? "on" : "off"}
				>
					<span className="tiptap-preset-dropdown-text">Table</span>
					<ChevronDownIcon className="tiptap-button-dropdown-small" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" aria-label="Table">
				{!inTable && (
					<DropdownMenuGroup>
						<DropdownMenuItem
							className="tiptap-dropdown-menu-radio-item"
							onSelect={() => run().insertStyledTable().run()}
						>
							Insert table (3 x 3)
						</DropdownMenuItem>
					</DropdownMenuGroup>
				)}
				{inTable && (
					<>
						<DropdownMenuGroup>
							<DropdownMenuLabel>Rows and columns</DropdownMenuLabel>
							<DropdownMenuItem
								className="tiptap-dropdown-menu-radio-item"
								onSelect={() => run().addRowBefore().run()}
							>
								Add row above
							</DropdownMenuItem>
							<DropdownMenuItem
								className="tiptap-dropdown-menu-radio-item"
								onSelect={() => run().addRowAfter().run()}
							>
								Add row below
							</DropdownMenuItem>
							<DropdownMenuItem
								className="tiptap-dropdown-menu-radio-item"
								onSelect={() => run().deleteRow().run()}
							>
								Delete row
							</DropdownMenuItem>
							<DropdownMenuItem
								className="tiptap-dropdown-menu-radio-item"
								onSelect={() => run().addColumnBefore().run()}
							>
								Add column left
							</DropdownMenuItem>
							<DropdownMenuItem
								className="tiptap-dropdown-menu-radio-item"
								onSelect={() => run().addColumnAfter().run()}
							>
								Add column right
							</DropdownMenuItem>
							<DropdownMenuItem
								className="tiptap-dropdown-menu-radio-item"
								onSelect={() => run().deleteColumn().run()}
							>
								Delete column
							</DropdownMenuItem>
						</DropdownMenuGroup>
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							<DropdownMenuLabel>Style</DropdownMenuLabel>
							{TABLE_FLAGS.map((flag) => (
								<DropdownMenuCheckboxItem
									key={flag.key}
									className="tiptap-dropdown-menu-radio-item"
									checked={state?.[flag.key] ?? false}
									onCheckedChange={(checked) =>
										run()
											.setTableStyle({ [flag.key]: checked })
											.run()
									}
								>
									{flag.label}
								</DropdownMenuCheckboxItem>
							))}
						</DropdownMenuGroup>
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							<DropdownMenuLabel>Header</DropdownMenuLabel>
							<DropdownMenuRadioGroup
								value={state?.header ?? "none"}
								onValueChange={(header) => {
									if (isTableHeaderKey(header)) run().setTableStyle({ header }).run();
								}}
							>
								{TABLE_HEADERS.map((header) => (
									<DropdownMenuRadioItem key={header.key} value={header.key}>
										{header.label}
									</DropdownMenuRadioItem>
								))}
							</DropdownMenuRadioGroup>
						</DropdownMenuGroup>
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							<DropdownMenuLabel>Text alignment</DropdownMenuLabel>
							<DropdownMenuRadioGroup
								value={state?.align ?? "left"}
								onValueChange={(align) => {
									if (isTableAlignKey(align)) run().setTableStyle({ align }).run();
								}}
							>
								{TABLE_ALIGNS.map((align) => (
									<DropdownMenuRadioItem key={align.key} value={align.key}>
										{align.label}
									</DropdownMenuRadioItem>
								))}
							</DropdownMenuRadioGroup>
						</DropdownMenuGroup>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							className="tiptap-dropdown-menu-radio-item"
							onSelect={() => run().deleteTable().run()}
						>
							Delete table
						</DropdownMenuItem>
					</>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
