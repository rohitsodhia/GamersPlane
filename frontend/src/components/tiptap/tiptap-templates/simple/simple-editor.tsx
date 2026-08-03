"use client";

import { FindAndReplace } from "@tiptap/extension-find-and-replace";
import { Highlight } from "@tiptap/extension-highlight";
import { Image } from "@tiptap/extension-image";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { Subscript } from "@tiptap/extension-subscript";
import { Superscript } from "@tiptap/extension-superscript";
import { TextAlign } from "@tiptap/extension-text-align";
import { Typography } from "@tiptap/extension-typography";
import { Selection } from "@tiptap/extensions";
import { EditorContent, EditorContext, useEditor } from "@tiptap/react";
// --- Tiptap Core Extensions ---
import { StarterKit } from "@tiptap/starter-kit";
import { useCallback, useEffect, useRef, useState } from "react";
import { HorizontalRule } from "#/components/tiptap/tiptap-node/horizontal-rule-node/horizontal-rule-node-extension";
// --- Tiptap Node ---
import { ImageUploadNode } from "#/components/tiptap/tiptap-node/image-upload-node/image-upload-node-extension";
// --- UI Primitives ---
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import { Spacer } from "#/components/tiptap/tiptap-ui-primitive/spacer";
import {
	Toolbar,
	ToolbarGroup,
	ToolbarSeparator,
} from "#/components/tiptap/tiptap-ui-primitive/toolbar";
import "#/components/tiptap/tiptap-node/blockquote-node/blockquote-node.scss";
import "#/components/tiptap/tiptap-node/code-block-node/code-block-node.scss";
import "#/components/tiptap/tiptap-node/horizontal-rule-node/horizontal-rule-node.scss";
import "#/components/tiptap/tiptap-node/list-node/list-node.scss";
import "#/components/tiptap/tiptap-node/image-node/image-node.scss";
import "#/components/tiptap/tiptap-node/heading-node/heading-node.scss";
import "#/components/tiptap/tiptap-node/paragraph-node/paragraph-node.scss";

// --- Icons ---
import { ArrowLeftIcon } from "#/components/tiptap/tiptap-icons/arrow-left-icon";
import { HighlighterIcon } from "#/components/tiptap/tiptap-icons/highlighter-icon";
import { LinkIcon } from "#/components/tiptap/tiptap-icons/link-icon";
// --- Components ---
import { ThemeToggle } from "#/components/tiptap/tiptap-templates/simple/theme-toggle";
import { BlockquoteButton } from "#/components/tiptap/tiptap-ui/blockquote-button";
import { CodeBlockButton } from "#/components/tiptap/tiptap-ui/code-block-button";
import {
	ColorHighlightPopover,
	ColorHighlightPopoverButton,
	ColorHighlightPopoverContent,
} from "#/components/tiptap/tiptap-ui/color-highlight-popover";
// --- Tiptap UI ---
import { HeadingDropdownMenu } from "#/components/tiptap/tiptap-ui/heading-dropdown-menu";
import { ImageUploadButton } from "#/components/tiptap/tiptap-ui/image-upload-button";
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
import { UndoRedoButton } from "#/components/tiptap/tiptap-ui/undo-redo-button";
import { useCursorVisibility } from "#/hooks/use-cursor-visibility";
// --- Hooks ---
import { useIsBreakpoint } from "#/hooks/use-is-breakpoint";
import { useWindowSize } from "#/hooks/use-window-size";

// --- Lib ---
import { handleImageUpload, MAX_FILE_SIZE } from "#/lib/tiptap-utils";

// --- Styles ---
import "#/components/tiptap/tiptap-templates/simple/simple-editor.scss";

import content from "#/components/tiptap/tiptap-templates/simple/data/content.json";

const SEARCH_AND_REPLACE_SCROLL_OPTIONS: ScrollIntoViewOptions = {
	block: "center",
};

const MainToolbarContent = ({
	onHighlighterClick,
	onLinkClick,
	onSearchAndReplaceClick,
	isSearchAndReplaceOpen,
	searchAndReplaceButtonRef,
	isMobile,
}: {
	onHighlighterClick: () => void;
	onLinkClick: () => void;
	onSearchAndReplaceClick: () => void;
	isSearchAndReplaceOpen: boolean;
	searchAndReplaceButtonRef: React.RefObject<HTMLButtonElement | null>;
	isMobile: boolean;
}) => {
	return (
		<>
			<Spacer />

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
					<ColorHighlightPopover />
				) : (
					<ColorHighlightPopoverButton onClick={onHighlighterClick} />
				)}
				{!isMobile ? <LinkPopover /> : <LinkButton onClick={onLinkClick} />}
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

			<ToolbarSeparator />

			<ToolbarGroup>
				<ImageUploadButton text="Add" />
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
				<ThemeToggle />
			</ToolbarGroup>
		</>
	);
};

const MobileToolbarContent = ({
	type,
	onBack,
}: {
	type: "highlighter" | "link";
	onBack: () => void;
}) => (
	<>
		<ToolbarGroup>
			<Button variant="ghost" onClick={onBack}>
				<ArrowLeftIcon className="tiptap-button-icon" />
				{type === "highlighter" ? (
					<HighlighterIcon className="tiptap-button-icon" />
				) : (
					<LinkIcon className="tiptap-button-icon" />
				)}
			</Button>
		</ToolbarGroup>

		<ToolbarSeparator />

		{type === "highlighter" ? <ColorHighlightPopoverContent /> : <LinkContent />}
	</>
);

export function SimpleEditor() {
	const isMobile = useIsBreakpoint();
	const { height } = useWindowSize();
	const [mobileView, setMobileView] = useState<"main" | "highlighter" | "link">("main");
	const [isSearchAndReplaceOpen, setIsSearchAndReplaceOpen] = useState(false);
	const toolbarRef = useRef<HTMLDivElement>(null);
	const searchAndReplaceButtonRef = useRef<HTMLButtonElement>(null);

	const editor = useEditor({
		immediatelyRender: false,
		editorProps: {
			attributes: {
				autocomplete: "off",
				autocorrect: "off",
				autocapitalize: "off",
				"aria-label": "Main content area, start typing to enter text.",
				class: "simple-editor",
			},
		},
		extensions: [
			StarterKit.configure({
				horizontalRule: false,
				link: {
					openOnClick: false,
					enableClickSelection: true,
				},
			}),
			HorizontalRule,
			TextAlign.configure({ types: ["heading", "paragraph"] }),
			TaskList,
			TaskItem.configure({ nested: true }),
			Highlight.configure({ multicolor: true }),
			Image,
			Typography,
			Superscript,
			Subscript,
			Selection,
			FindAndReplace.configure({
				searchDebounceMs: 500,
				injectCSS: false,
			}),
			ImageUploadNode.configure({
				accept: "image/*",
				maxSize: MAX_FILE_SIZE,
				limit: 3,
				upload: handleImageUpload,
				onError: (error) => console.error("Upload failed:", error),
			}),
		],
		content,
	});

	const rect = useCursorVisibility({
		editor,
		overlayHeight: toolbarRef.current?.getBoundingClientRect().height ?? 0,
	});

	useEffect(() => {
		if (!isMobile && mobileView !== "main") {
			setMobileView("main");
		}
	}, [isMobile, mobileView]);

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

	return (
		<div className="simple-editor-wrapper">
			<EditorContext.Provider value={{ editor }}>
				<Toolbar
					ref={toolbarRef}
					style={{
						...(isMobile
							? {
									bottom: `calc(100% - ${height - rect.y}px)`,
								}
							: {}),
					}}
				>
					{mobileView === "main" ? (
						<MainToolbarContent
							onHighlighterClick={() => setMobileView("highlighter")}
							onLinkClick={() => setMobileView("link")}
							onSearchAndReplaceClick={toggleSearchAndReplace}
							isSearchAndReplaceOpen={isSearchAndReplaceOpen}
							searchAndReplaceButtonRef={searchAndReplaceButtonRef}
							isMobile={isMobile}
						/>
					) : (
						<MobileToolbarContent
							type={mobileView === "highlighter" ? "highlighter" : "link"}
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
					className="simple-editor-content"
				/>
			</EditorContext.Provider>
		</div>
	);
}
