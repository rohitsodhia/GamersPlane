import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import {
	FLOATS,
	type FloatKey,
	isFloatKey,
} from "#/components/tiptap/tiptap-extension/float-attribute";
import { ChevronDownIcon } from "#/components/tiptap/tiptap-icons/chevron-down-icon";
import {
	BOX_NODE_NAME,
	BOX_VARIANTS,
	isBoxVariantKey,
} from "#/components/tiptap/tiptap-node/box-node/box-node-extension";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import {
	DropdownMenu,
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

function FloatRadioItems({
	value,
	onChange,
}: {
	value: FloatKey;
	onChange: (float: FloatKey) => void;
}) {
	return (
		<DropdownMenuRadioGroup
			value={value}
			onValueChange={(next) => {
				if (isFloatKey(next)) onChange(next);
			}}
		>
			{FLOATS.map((float) => (
				<DropdownMenuRadioItem key={float.key} value={float.key}>
					{float.label}
				</DropdownMenuRadioItem>
			))}
		</DropdownMenuRadioGroup>
	);
}

/**
 * Inserts a box in one of its variants. With the caret in a box, the same choices
 * pick that box's variant (the current one is checked), and the menu adds a Float
 * section and "Remove box".
 */
export function BoxDropdown({ editor: providedEditor }: { editor?: Editor | null }) {
	const { editor } = useTiptapEditor(providedEditor);
	const state = useEditorState({
		editor,
		selector: ({ editor }) => {
			// The button renders whenever the editor exists; this state can still be
			// empty on the first render, which is why it is not used to hide it.
			if (!editor) return { inBox: false, variant: "", float: "none" };
			const inBox = editor.isActive(BOX_NODE_NAME);
			const attrs = editor.getAttributes(BOX_NODE_NAME);
			return {
				inBox,
				variant: inBox && isBoxVariantKey(attrs["variant"]) ? attrs["variant"] : "",
				float: inBox && isFloatKey(attrs["float"]) ? attrs["float"] : "none",
			};
		},
	});

	if (!editor) return null;
	const inBox = state?.inBox ?? false;

	return (
		<DropdownMenu modal={false}>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label="Box"
					tooltip="Box"
					data-active-state={inBox ? "on" : "off"}
				>
					<span className="tiptap-preset-dropdown-text">Box</span>
					<ChevronDownIcon className="tiptap-button-dropdown-small" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" aria-label="Box">
				<DropdownMenuGroup>
					<DropdownMenuRadioGroup
						value={state?.variant ?? ""}
						onValueChange={(variant) => {
							if (isBoxVariantKey(variant)) {
								editor.chain().focus().setBox({ variant }).run();
							}
						}}
					>
						{BOX_VARIANTS.map((variant) => (
							<DropdownMenuRadioItem key={variant.key} value={variant.key}>
								{variant.label}
							</DropdownMenuRadioItem>
						))}
					</DropdownMenuRadioGroup>
				</DropdownMenuGroup>
				{inBox && (
					<>
						<DropdownMenuSeparator />
						<DropdownMenuGroup>
							<DropdownMenuLabel>Float</DropdownMenuLabel>
							<FloatRadioItems
								value={(state?.float ?? "none") as FloatKey}
								onChange={(float) => editor.chain().focus().updateBox({ float }).run()}
							/>
						</DropdownMenuGroup>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							className="tiptap-dropdown-menu-radio-item"
							onSelect={() => editor.chain().focus().unsetBox().run()}
						>
							Remove box
						</DropdownMenuItem>
					</>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

/** Floats the selected image. Shown only while an image is selected. */
export function ImageFloatDropdown({
	editor: providedEditor,
}: {
	editor?: Editor | null;
}) {
	const { editor } = useTiptapEditor(providedEditor);
	const state = useEditorState({
		editor,
		selector: ({ editor }) => {
			if (!editor?.isEditable || !editor.isActive("image")) {
				return { selected: false, float: "none" };
			}
			const float: unknown = editor.getAttributes("image")["float"];
			return { selected: true, float: isFloatKey(float) ? float : "none" };
		},
	});

	if (!editor || !state?.selected) return null;

	return (
		<DropdownMenu modal={false}>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label="Image float"
					tooltip="Image float"
					data-active-state={state.float === "none" ? "off" : "on"}
				>
					<span className="tiptap-preset-dropdown-text">Float</span>
					<ChevronDownIcon className="tiptap-button-dropdown-small" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" aria-label="Image float">
				<DropdownMenuGroup>
					<FloatRadioItems
						value={state.float as FloatKey}
						onChange={(float) => editor.chain().focus().setImageFloat(float).run()}
					/>
				</DropdownMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
