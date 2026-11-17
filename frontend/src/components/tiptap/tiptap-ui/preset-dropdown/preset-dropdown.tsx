import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import { ChevronDownIcon } from "#/components/tiptap/tiptap-icons/chevron-down-icon";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuTrigger,
} from "#/components/tiptap/tiptap-ui-primitive/dropdown-menu";
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

import "#/components/tiptap/tiptap-ui/preset-dropdown/preset-dropdown.scss";

export type PresetOption = { key: string; label: string };

/**
 * A toolbar dropdown choosing one of a fixed set of presets, or "none". Used by the
 * font size and font family marks, which store only the preset key. When
 * `previewAttribute` is set (e.g. `data-font`), each label carries that attribute
 * with its key so the page's stylesheet shows it in its own typeface.
 */
export function PresetDropdown({
	editor: providedEditor,
	ariaLabel,
	defaultLabel,
	normalLabel,
	options,
	readActive,
	onSelect,
	previewAttribute,
}: {
	editor?: Editor | null;
	/** Names the trigger and menu, e.g. "Font size". */
	ariaLabel: string;
	/** The trigger text when no preset is set, e.g. "Size". */
	defaultLabel: string;
	/** The menu's first choice, which sets nothing (removes the mark), e.g. "Default". */
	normalLabel: string;
	options: readonly PresetOption[];
	/** The preset key at the selection, or null when there is none. */
	readActive: (editor: Editor) => string | null;
	/** Applies `key`; `null` removes the mark. */
	onSelect: (editor: Editor, key: string | null) => void;
	previewAttribute?: string;
}) {
	const { editor } = useTiptapEditor(providedEditor);
	const active = useEditorState({
		editor,
		selector: ({ editor }) => (editor ? readActive(editor) : null),
	});

	if (!editor) return null;

	const activeOption = options.find((option) => option.key === active);
	const preview = (key: string) =>
		previewAttribute ? { [previewAttribute]: key } : {};

	return (
		<DropdownMenu modal={false}>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label={ariaLabel}
					tooltip={ariaLabel}
					data-active-state={activeOption ? "on" : "off"}
				>
					<span
						className="tiptap-preset-dropdown-text"
						{...(activeOption ? preview(activeOption.key) : {})}
					>
						{activeOption?.label ?? defaultLabel}
					</span>
					<ChevronDownIcon className="tiptap-button-dropdown-small" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" aria-label={ariaLabel}>
				<DropdownMenuGroup>
					<DropdownMenuRadioGroup
						value={activeOption?.key ?? ""}
						onValueChange={(value) => onSelect(editor, value === "" ? null : value)}
					>
						<DropdownMenuRadioItem value="">{normalLabel}</DropdownMenuRadioItem>
						{options.map((option) => (
							<DropdownMenuRadioItem key={option.key} value={option.key}>
								<span {...preview(option.key)}>{option.label}</span>
							</DropdownMenuRadioItem>
						))}
					</DropdownMenuRadioGroup>
				</DropdownMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
