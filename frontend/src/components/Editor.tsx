import type { JSONContent } from "@tiptap/core";
import { Color } from "@tiptap/extension-color";
import { FindAndReplace } from "@tiptap/extension-find-and-replace";
import { Image } from "@tiptap/extension-image";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { Subscript } from "@tiptap/extension-subscript";
import { Superscript } from "@tiptap/extension-superscript";
import { TextAlign } from "@tiptap/extension-text-align";
import { TextStyle } from "@tiptap/extension-text-style";
import { Typography } from "@tiptap/extension-typography";
import { Selection } from "@tiptap/extensions";
import { AllSelection } from "@tiptap/pm/state";
import type { Editor as TiptapEditor } from "@tiptap/react";
import { EditorContent, EditorContext, useEditor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { StarterKit } from "@tiptap/starter-kit";
import clsx from "clsx";
import type { ComponentProps } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// --- Tiptap node styles ---
import { HorizontalRule } from "#/components/tiptap/tiptap-node/horizontal-rule-node/horizontal-rule-node-extension";
import { Note } from "#/components/tiptap/tiptap-node/note-node/note-node-extension";
import "#/components/tiptap/tiptap-node/blockquote-node/blockquote-node.scss";
import "#/components/tiptap/tiptap-node/code-block-node/code-block-node.scss";
import "#/components/tiptap/tiptap-node/horizontal-rule-node/horizontal-rule-node.scss";
import "#/components/tiptap/tiptap-node/list-node/list-node.scss";
import "#/components/tiptap/tiptap-node/image-node/image-node.scss";
import "#/components/tiptap/tiptap-node/heading-node/heading-node.scss";
import "#/components/tiptap/tiptap-node/paragraph-node/paragraph-node.scss";
import "#/components/tiptap/tiptap-node/note-node/note-node.scss";

// --- Icons ---
import { ArrowLeftIcon } from "#/components/tiptap/tiptap-icons/arrow-left-icon";
import { CaseSensitiveIcon } from "#/components/tiptap/tiptap-icons/case-sensitive-icon";
import { CornerDownLeftIcon } from "#/components/tiptap/tiptap-icons/corner-down-left-icon";
import { HorizontalRuleIcon } from "#/components/tiptap/tiptap-icons/horizontal-rule-icon";
import { ImagePlusIcon } from "#/components/tiptap/tiptap-icons/image-plus-icon";
import { LinkIcon } from "#/components/tiptap/tiptap-icons/link-icon";
// --- Tiptap UI ---
import { BlockquoteButton } from "#/components/tiptap/tiptap-ui/blockquote-button";
import { CodeBlockButton } from "#/components/tiptap/tiptap-ui/code-block-button";
import { HeadingDropdownMenu } from "#/components/tiptap/tiptap-ui/heading-dropdown-menu";
import {
	LinkButton,
	LinkContent,
	LinkPopover,
} from "#/components/tiptap/tiptap-ui/link-popover";
import { ListDropdownMenu } from "#/components/tiptap/tiptap-ui/list-dropdown-menu";
import { MarkButton } from "#/components/tiptap/tiptap-ui/mark-button";
import {
	SearchAndReplace,
	SearchAndReplaceButton,
} from "#/components/tiptap/tiptap-ui/search-and-replace";
import { TextAlignButton } from "#/components/tiptap/tiptap-ui/text-align-button";
import {
	TextColorPopover,
	TextColorPopoverButton,
	TextColorPopoverContent,
} from "#/components/tiptap/tiptap-ui/text-color-popover";
import { UndoRedoButton } from "#/components/tiptap/tiptap-ui/undo-redo-button";
// --- UI primitives ---
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import { Spacer } from "#/components/tiptap/tiptap-ui-primitive/spacer";
import {
	Toolbar,
	ToolbarGroup,
	ToolbarSeparator,
} from "#/components/tiptap/tiptap-ui-primitive/toolbar";

// --- Hooks ---
import { useCursorVisibility } from "#/hooks/use-cursor-visibility";
import { useIsBreakpoint } from "#/hooks/use-is-breakpoint";
import { useWindowSize } from "#/hooks/use-window-size";

// --- Styles ---
import "#/components/tiptap/tiptap-templates/simple/simple-editor.scss";

export const emptyContent: JSONContent = { type: "doc", content: [] };

export function isContentEmpty(content: JSONContent | null | undefined): boolean {
	if (!content) return true;
	if (content.text) return false;
	return (content.content ?? []).every(isContentEmpty);
}

// StarterKit's TrailingNode extension appends an empty paragraph after a
// document-final node that can't otherwise be typed into directly (e.g. our
// isolating Note node), purely so there's somewhere to click while editing.
// It carries no meaning outside the editor, so read-only rendering should
// drop it rather than showing a stray empty line.
export function trimTrailingEmptyParagraph(content: JSONContent): JSONContent {
	const nodes = content.content ?? [];
	const last = nodes[nodes.length - 1];
	if (nodes.length <= 1 || last?.type !== "paragraph" || !isContentEmpty(last)) {
		return content;
	}
	return { ...content, content: nodes.slice(0, -1) };
}

const SEARCH_AND_REPLACE_SCROLL_OPTIONS: ScrollIntoViewOptions = {
	block: "center",
};

// No dedicated "insert line break" button ships with the tiptap templates
// (Shift+Enter covers it), but markItUp had one, so wire the existing
// StarterKit HardBreak command up to a toolbar button.
function LineBreakButton({ editor }: { editor: TiptapEditor | null }) {
	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Line break"
			aria-label="Line break"
			onClick={() => editor.chain().focus().setHardBreak().run()}
		>
			<CornerDownLeftIcon className="tiptap-button-icon" />
		</Button>
	);
}

// No dedicated horizontal rule button ships with the tiptap templates either;
// wire up the custom HorizontalRule extension's command directly.
function HorizontalRuleButton({ editor }: { editor: TiptapEditor | null }) {
	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Horizontal break"
			aria-label="Horizontal rule"
			onClick={() => editor.chain().focus().setHorizontalRule().run()}
		>
			<HorizontalRuleIcon className="tiptap-button-icon" />
		</Button>
	);
}

// No dedicated note button ships with the tiptap templates either; wire up
// the custom Note extension's command directly, same as the horizontal rule.
function NoteButton({ editor }: { editor: TiptapEditor | null }) {
	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Note"
			aria-label="Note"
			onClick={() => editor.chain().focus().setNote().run()}
		>
			Note
		</Button>
	);
}

// The template's ImageUploadButton needs a real upload endpoint we don't have
// yet. Inserting by URL needs no backend, so wire that up with the installed
// Image extension instead, matching markItUp's "By URL..." option.
function ImageUrlButton({ editor }: { editor: TiptapEditor | null }) {
	const handleClick = useCallback(() => {
		if (!editor) return;
		const url = window.prompt("Image URL");
		if (!url) return;
		editor.chain().focus().setImage({ src: url }).run();
	}, [editor]);

	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Image by URL"
			aria-label="Image by URL"
			onClick={handleClick}
		>
			<ImagePlusIcon className="tiptap-button-icon" />
		</Button>
	);
}

const MainToolbarContent = ({
	editor,
	onTextColorClick,
	onLinkClick,
	onSearchAndReplaceClick,
	isSearchAndReplaceOpen,
	searchAndReplaceButtonRef,
	isMobile,
}: {
	editor: TiptapEditor | null;
	onTextColorClick: () => void;
	onLinkClick: () => void;
	onSearchAndReplaceClick: () => void;
	isSearchAndReplaceOpen: boolean;
	searchAndReplaceButtonRef: React.RefObject<HTMLButtonElement | null>;
	isMobile: boolean;
}) => {
	return (
		<>
			{/* <Spacer /> */}

			<ToolbarGroup>
				<UndoRedoButton action="undo" />
				<UndoRedoButton action="redo" />
			</ToolbarGroup>

			<ToolbarSeparator />

			<ToolbarGroup>
				<HeadingDropdownMenu modal={false} levels={[1, 2, 3, 4]} />
				<ListDropdownMenu
					modal={false}
					types={["bulletList", "orderedList", "taskList"]}
				/>
				<BlockquoteButton />
				<CodeBlockButton />
			</ToolbarGroup>

			<ToolbarSeparator />

			<ToolbarGroup>
				<MarkButton type="bold" />
				<MarkButton type="italic" />
				<MarkButton type="strike" />
				<MarkButton type="code" />
				<MarkButton type="underline" />
				{!isMobile ? (
					<TextColorPopover />
				) : (
					<TextColorPopoverButton onClick={onTextColorClick} />
				)}
				{!isMobile ? <LinkPopover /> : <LinkButton onClick={onLinkClick} />}
				<ImageUrlButton editor={editor} />
				<HorizontalRuleButton editor={editor} />
				<NoteButton editor={editor} />
			</ToolbarGroup>

			<ToolbarSeparator />

			<ToolbarGroup>
				<MarkButton type="superscript" />
				<MarkButton type="subscript" />
			</ToolbarGroup>

			<ToolbarSeparator />

			<ToolbarGroup>
				<TextAlignButton align="left" />
				<TextAlignButton align="center" />
				<TextAlignButton align="right" />
				<TextAlignButton align="justify" />
			</ToolbarGroup>

			<Spacer />

			{isMobile && <ToolbarSeparator />}

			<ToolbarGroup>
				<SearchAndReplaceButton
					ref={searchAndReplaceButtonRef}
					aria-expanded={isSearchAndReplaceOpen}
					data-active-state={isSearchAndReplaceOpen ? "on" : "off"}
					onClick={onSearchAndReplaceClick}
				/>
			</ToolbarGroup>
		</>
	);
};

const MobileToolbarContent = ({
	type,
	onBack,
}: {
	type: "color" | "link";
	onBack: () => void;
}) => (
	<>
		<ToolbarGroup>
			<Button variant="ghost" onClick={onBack}>
				<ArrowLeftIcon className="tiptap-button-icon" />
				{type === "color" ? (
					<CaseSensitiveIcon className="tiptap-button-icon" />
				) : (
					<LinkIcon className="tiptap-button-icon" />
				)}
			</Button>
		</ToolbarGroup>

		<ToolbarSeparator />

		{type === "color" ? <TextColorPopoverContent /> : <LinkContent />}
	</>
);

// Tiptap's default shouldShow only treats a `TextSelection` as "empty text",
// but clicking into an empty document produces an `AllSelection` instead
// (from 0 to the size of the empty paragraph), which slips past that check
// and shows the bubble menu with nothing highlighted. Checking the selected
// text length directly covers every selection type.
const bubbleMenuShouldShow: NonNullable<
	ComponentProps<typeof BubbleMenu>["shouldShow"]
> = ({ editor, state, from, to }) => {
	if (!editor.isEditable || state.selection.empty) return false;
	return state.doc.textBetween(from, to).length > 0;
};

// Selection-driven inline formatting, shown next to highlighted text.
const BubbleMenuContent = () => (
	<Toolbar variant="floating">
		<ToolbarGroup>
			<MarkButton type="bold" />
			<MarkButton type="italic" />
			<MarkButton type="underline" />
			<MarkButton type="strike" />
			<LinkPopover />
		</ToolbarGroup>
	</Toolbar>
);

type EditorProps = {
	id?: string;
	value: JSONContent | null | undefined;
	onChange: (value: JSONContent) => void;
	onBlur?: () => void;
	className?: string;
};

const Editor = ({ id, value, onChange, onBlur, className }: EditorProps) => {
	const isMobile = useIsBreakpoint();
	const { height } = useWindowSize();
	const [mobileView, setMobileView] = useState<"main" | "color" | "link">("main");
	const [isSearchAndReplaceOpen, setIsSearchAndReplaceOpen] = useState(false);
	const toolbarRef = useRef<HTMLDivElement>(null);
	const searchAndReplaceButtonRef = useRef<HTMLButtonElement>(null);

	const editor = useEditor({
		immediatelyRender: false,
		extensions: [
			StarterKit.configure({
				horizontalRule: false,
				hardBreak: false,
				link: {
					openOnClick: false,
					enableClickSelection: true,
				},
			}),
			HorizontalRule,
			Note,
			TextAlign.configure({ types: ["heading", "paragraph"] }),
			TaskList,
			TaskItem.configure({ nested: true }),
			TextStyle,
			Color,
			Image,
			Typography,
			Superscript,
			Subscript,
			Selection,
			FindAndReplace.configure({
				searchDebounceMs: 500,
				injectCSS: false,
			}),
		],
		content: value ?? emptyContent,
		onUpdate: ({ editor }) => {
			onChange(editor.getJSON());
		},
		onBlur: () => {
			onBlur?.();
		},
		// Clicking into (or tabbing into) an editor whose doc has no real
		// content resolves to an AllSelection covering the whole (empty) doc
		// instead of a collapsed cursor, which visually looks like the empty
		// area got ctrl+a'd. Collapse it to a normal cursor at the start.
		onFocus: ({ editor }) => {
			if (editor.state.selection instanceof AllSelection) {
				editor.commands.setTextSelection(0);
			}
		},
		editorProps: {
			attributes: {
				autocomplete: "off",
				autocorrect: "off",
				autocapitalize: "off",
				class: "simple-editor",
				...(id ? { id } : {}),
			},
		},
	});

	// Only relevant when the toolbar floats over content (mobile, overlapping
	// the virtual keyboard). On desktop the toolbar is static and the page can
	// legitimately be taller than the viewport, so this hook's scroll
	// correction would otherwise fight the browser's native scroll-into-view.
	const rect = useCursorVisibility({
		editor: isMobile ? editor : null,
		overlayHeight: toolbarRef.current?.getBoundingClientRect().height ?? 0,
	});

	useEffect(() => {
		if (!isMobile && mobileView !== "main") {
			setMobileView("main");
		}
	}, [isMobile, mobileView]);

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

	const openSearchAndReplace = useCallback(() => {
		setMobileView("main");
		setIsSearchAndReplaceOpen(true);
	}, []);

	const closeSearchAndReplace = useCallback(() => {
		setIsSearchAndReplaceOpen(false);
		searchAndReplaceButtonRef.current?.focus();
	}, []);

	const toggleSearchAndReplace = useCallback(() => {
		if (isSearchAndReplaceOpen) {
			closeSearchAndReplace();
			return;
		}
		openSearchAndReplace();
	}, [closeSearchAndReplace, isSearchAndReplaceOpen, openSearchAndReplace]);

	// Memoize the provider value to avoid unnecessary re-renders
	const providerValue = useMemo(() => ({ editor }), [editor]);

	return (
		<div className="tiptap-editor simple-editor-wrapper">
			<EditorContext.Provider value={providerValue}>
				<Toolbar
					ref={toolbarRef}
					style={{
						...(isMobile ? { bottom: `calc(100% - ${height - rect.y}px)` } : {}),
					}}
				>
					{mobileView === "main" ? (
						<MainToolbarContent
							editor={editor}
							onTextColorClick={() => setMobileView("color")}
							onLinkClick={() => setMobileView("link")}
							onSearchAndReplaceClick={toggleSearchAndReplace}
							isSearchAndReplaceOpen={isSearchAndReplaceOpen}
							searchAndReplaceButtonRef={searchAndReplaceButtonRef}
							isMobile={isMobile}
						/>
					) : (
						<MobileToolbarContent
							type={mobileView === "color" ? "color" : "link"}
							onBack={() => setMobileView("main")}
						/>
					)}
				</Toolbar>

				<SearchAndReplace
					className="simple-editor-search-and-replace"
					open={isSearchAndReplaceOpen}
					onOpen={openSearchAndReplace}
					onClose={closeSearchAndReplace}
					scrollIntoViewOptions={SEARCH_AND_REPLACE_SCROLL_OPTIONS}
				/>

				<EditorContent
					editor={editor}
					role="presentation"
					className={clsx("simple-editor-content", className)}
				/>

				{editor && (
					<BubbleMenu
						className="simple-editor-bubble-menu"
						shouldShow={bubbleMenuShouldShow}
					>
						<BubbleMenuContent />
					</BubbleMenu>
				)}
			</EditorContext.Provider>
		</div>
	);
};

export default Editor;
