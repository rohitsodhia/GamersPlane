import type { JSONContent } from "@tiptap/core";
import { Color } from "@tiptap/extension-color";
import { FindAndReplace } from "@tiptap/extension-find-and-replace";
import { Link } from "@tiptap/extension-link";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { Subscript } from "@tiptap/extension-subscript";
import { Superscript } from "@tiptap/extension-superscript";
import { TextAlign } from "@tiptap/extension-text-align";
import { TextStyle } from "@tiptap/extension-text-style";
import { Typography } from "@tiptap/extension-typography";
import { Selection } from "@tiptap/extensions";
import { AllSelection } from "@tiptap/pm/state";
import type { Editor as TiptapEditor } from "@tiptap/react";
import { EditorContent, EditorContext, useEditor, useEditorState } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// --- Tiptap node styles ---
import { FontFamily } from "#/components/tiptap/tiptap-extension/font-family-extension";
import { FontSize } from "#/components/tiptap/tiptap-extension/font-size-extension";
import { BannerHeading } from "#/components/tiptap/tiptap-extension/heading-extension";
import { SafeHighlight } from "#/components/tiptap/tiptap-extension/highlight-extension";
import { FloatImage } from "#/components/tiptap/tiptap-extension/image-extension";
import { isAllowedLinkUri } from "#/components/tiptap/tiptap-extension/link-options";
import { SafeOrderedList } from "#/components/tiptap/tiptap-extension/ordered-list-extension";
import { Box } from "#/components/tiptap/tiptap-node/box-node/box-node-extension";
import {
	Column,
	Columns,
} from "#/components/tiptap/tiptap-node/columns-node/columns-node-extension";
import { HorizontalRule } from "#/components/tiptap/tiptap-node/horizontal-rule-node/horizontal-rule-node-extension";
import {
	addMentions,
	type ContentMention,
	findMentionNames,
} from "#/components/tiptap/tiptap-node/mention-node/mention";
import {
	Mention,
	MentionContext,
} from "#/components/tiptap/tiptap-node/mention-node/mention-node-extension";
import { useMentionPicker } from "#/components/tiptap/tiptap-node/mention-node/mention-picker";
import {
	Note,
	NoteContext,
} from "#/components/tiptap/tiptap-node/note-node/note-node-extension";
import { NpcRoster } from "#/components/tiptap/tiptap-node/npc-roster-node/npc-roster-node-extension";
import {
	NpcSpeaker,
	NpcSpeakerContext,
} from "#/components/tiptap/tiptap-node/npc-speaker-node/npc-speaker-node-extension";
import {
	hasPoll,
	Poll,
} from "#/components/tiptap/tiptap-node/poll-node/poll-node-extension";
import { Quote } from "#/components/tiptap/tiptap-node/quote-node/quote-node-extension";
import { Spoiler } from "#/components/tiptap/tiptap-node/spoiler-node/spoiler-node-extension";
import { TABLE_EXTENSIONS } from "#/components/tiptap/tiptap-node/table-node/table-node-extension";
import { Youtube } from "#/components/tiptap/tiptap-node/youtube-node/youtube-node-extension";
import type { SearchUser } from "#/queries/users";
import "#/components/tiptap/tiptap-extension/font-faces";
import "#/components/tiptap/tiptap-extension/text-format.scss";
import "#/components/tiptap/tiptap-node/blockquote-node/blockquote-node.scss";
import "#/components/tiptap/tiptap-node/box-node/box-node.scss";
import "#/components/tiptap/tiptap-node/code-block-node/code-block-node.scss";
import "#/components/tiptap/tiptap-node/columns-node/columns-node.scss";
import "#/components/tiptap/tiptap-node/horizontal-rule-node/horizontal-rule-node.scss";
import "#/components/tiptap/tiptap-node/list-node/list-node.scss";
import "#/components/tiptap/tiptap-node/image-node/image-node.scss";
import "#/components/tiptap/tiptap-node/heading-node/heading-node.scss";
import "#/components/tiptap/tiptap-node/paragraph-node/paragraph-node.scss";
import "#/components/tiptap/tiptap-node/mention-node/mention-node.scss";
import "#/components/tiptap/tiptap-node/note-node/note-node.scss";
import "#/components/tiptap/tiptap-node/npc-roster-node/npc-roster-node.scss";
import "#/components/tiptap/tiptap-node/npc-speaker-node/npc-speaker-node.scss";
import "#/components/tiptap/tiptap-node/poll-node/poll-node.scss";
import "#/components/tiptap/tiptap-node/quote-node/quote-node.scss";
import "#/components/tiptap/tiptap-node/spoiler-node/spoiler-node.scss";
import "#/components/tiptap/tiptap-node/table-node/table-node.scss";
import "#/components/tiptap/tiptap-node/youtube-node/youtube-node.scss";

import { NpcChooser } from "#/components/NpcChooser";
// --- Icons ---
import { ArrowLeftIcon } from "#/components/tiptap/tiptap-icons/arrow-left-icon";
import { CaseSensitiveIcon } from "#/components/tiptap/tiptap-icons/case-sensitive-icon";
import { HorizontalRuleIcon } from "#/components/tiptap/tiptap-icons/horizontal-rule-icon";
import { ImagePlusIcon } from "#/components/tiptap/tiptap-icons/image-plus-icon";
import { LinkIcon } from "#/components/tiptap/tiptap-icons/link-icon";
// --- Tiptap UI ---
import { BlockquoteButton } from "#/components/tiptap/tiptap-ui/blockquote-button";
import {
	BoxDropdown,
	ImageFloatDropdown,
} from "#/components/tiptap/tiptap-ui/box-dropdown/box-dropdown";
import { CodeBlockButton } from "#/components/tiptap/tiptap-ui/code-block-button";
import { ColumnsDropdown } from "#/components/tiptap/tiptap-ui/columns-dropdown/columns-dropdown";
import { HeadingDropdownMenu } from "#/components/tiptap/tiptap-ui/heading-dropdown-menu";
import { HighlightPopover } from "#/components/tiptap/tiptap-ui/highlight-popover/highlight-popover";
import { ImageLinkPopover } from "#/components/tiptap/tiptap-ui/image-link-popover/image-link-popover";
import {
	LinkButton,
	LinkContent,
	LinkPopover,
} from "#/components/tiptap/tiptap-ui/link-popover";
import { ListDropdownMenu } from "#/components/tiptap/tiptap-ui/list-dropdown-menu";
import { MarkButton } from "#/components/tiptap/tiptap-ui/mark-button";
import { OrderedListOptions } from "#/components/tiptap/tiptap-ui/ordered-list-options/ordered-list-options";
import {
	FontFamilyDropdown,
	FontSizeDropdown,
} from "#/components/tiptap/tiptap-ui/preset-dropdown/font-dropdowns";
import {
	SearchAndReplace,
	SearchAndReplaceButton,
} from "#/components/tiptap/tiptap-ui/search-and-replace";
import { TableDropdown } from "#/components/tiptap/tiptap-ui/table-dropdown/table-dropdown";
import { TextAlignButton } from "#/components/tiptap/tiptap-ui/text-align-button";
import {
	TextColorPopover,
	TextColorPopoverButton,
	TextColorPopoverContent,
} from "#/components/tiptap/tiptap-ui/text-color-popover";
import { UndoRedoButton } from "#/components/tiptap/tiptap-ui/undo-redo-button";
import { YoutubePopover } from "#/components/tiptap/tiptap-ui/youtube-popover/youtube-popover";
// --- UI primitives ---
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import {
	Toolbar,
	ToolbarGroup,
	ToolbarSeparator,
} from "#/components/tiptap/tiptap-ui-primitive/toolbar";
// --- Hooks ---
import { useCursorVisibility } from "#/hooks/use-cursor-visibility";
import { useIsBreakpoint } from "#/hooks/use-is-breakpoint";
import { useWindowSize } from "#/hooks/use-window-size";
import type { ContentNpc, NpcLibrary } from "#/queries/quick-npcs";

// --- Styles ---
import "#/components/tiptap/tiptap-templates/simple/simple-editor.scss";

// The default Link extension marks itself inclusive (tied to the `autolink`
// option), which extends the link mark to the cursor placed right after a
// link. That makes it impossible to type plain text immediately after a
// link, so it's overridden here to behave like a normal exclusive mark.
const NonInclusiveLink = Link.extend({
	inclusive() {
		return false;
	},
});

export const emptyContent: JSONContent = { type: "doc", content: [] };

// Nodes that hold no text but are content in their own right, so a post made of
// just one of them isn't empty.
const CONTENT_ATOMS = new Set(["image", "npcRoster", "youtube"]);

export function isContentEmpty(content: JSONContent | null | undefined): boolean {
	if (!content) return true;
	if (content.text) return false;
	if (content.type && CONTENT_ATOMS.has(content.type)) return false;
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

// No dedicated quote button ships with the tiptap templates either; wire up
// the custom Quote extension's command directly, same as the note button.
function QuoteButton({ editor }: { editor: TiptapEditor | null }) {
	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Quote"
			aria-label="Quote"
			onClick={() => editor.chain().focus().setQuote().run()}
		>
			Quote
		</Button>
	);
}

// Out-of-character aside: a variant of the quote node. Marked on while the caret is
// in one; clicking then takes the content back out, and in a plain quote it turns
// that quote into an OOC block. Always rendered once the editor exists: the editor
// state below is empty on the first render, so it must not decide visibility.
function OocButton({ editor }: { editor: TiptapEditor | null }) {
	const isActive = useEditorState({
		editor,
		selector: ({ editor }) => editor?.isActive("quote", { variant: "ooc" }) ?? false,
	});

	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Out of character"
			aria-label="Out of character"
			data-active-state={isActive ? "on" : "off"}
			onClick={() => editor.chain().focus().toggleOoc().run()}
		>
			OOC
		</Button>
	);
}

// A collapsible block with a title. Same on/off behavior as the OOC button.
function SpoilerButton({ editor }: { editor: TiptapEditor | null }) {
	const isActive = useEditorState({
		editor,
		selector: ({ editor }) => editor?.isActive("spoiler") ?? false,
	});

	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Spoiler"
			aria-label="Spoiler"
			data-active-state={isActive ? "on" : "off"}
			onClick={() => editor.chain().focus().toggleSpoiler().run()}
		>
			Spoiler
		</Button>
	);
}

// Marks where the thread's poll appears in the post. Only passed the thread's first
// post (see `pollAvailable`); a document holds one marker, so the button is disabled
// once there is one. Whether it is disabled is read from the editor on each render
// (the subscription below only triggers that render), since the subscribed state is
// empty on the first one.
function PollButton({ editor }: { editor: TiptapEditor | null }) {
	useEditorState({
		editor,
		selector: ({ editor }) => (editor ? hasPoll(editor.state.doc) : false),
	});

	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="Place the thread's poll here"
			aria-label="Poll"
			disabled={hasPoll(editor.state.doc)}
			onClick={() => editor.chain().focus().insertPoll().run()}
		>
			Poll
		</Button>
	);
}

// Opens the speaker chooser; picking (or making) a quick NPC wraps the selection in
// one of its speech blocks. Only shown where the editor was given an NPC library.
function NpcSpeakerButton({
	editor,
	library,
}: {
	editor: TiptapEditor | null;
	library: NpcLibrary;
}) {
	const [isChoosing, setIsChoosing] = useState(false);
	const buttonRef = useRef<HTMLButtonElement>(null);

	if (!editor) return null;

	return (
		<>
			<Button
				ref={buttonRef}
				type="button"
				variant="ghost"
				tooltip="NPC speech"
				aria-label="NPC speech"
				aria-haspopup="dialog"
				onClick={() => setIsChoosing(true)}
			>
				NPC
			</Button>
			<NpcChooser
				library={library}
				isOpen={isChoosing}
				onOpenChange={setIsChoosing}
				triggerRef={buttonRef}
				onChoose={(npc) =>
					editor.chain().focus().setNpcSpeaker({ npcId: npc.id }).run()
				}
			/>
		</>
	);
}

// Inserts an empty roster (a titled grid of NPC portraits) to fill in. Only shown
// where the editor was given an NPC library, like the speaker button.
function NpcRosterButton({ editor }: { editor: TiptapEditor | null }) {
	if (!editor) return null;

	return (
		<Button
			type="button"
			variant="ghost"
			tooltip="NPC roster"
			aria-label="NPC roster"
			onClick={() => editor.chain().focus().insertNpcRoster().run()}
		>
			Roster
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
	npcLibrary,
	pollAvailable,
}: {
	editor: TiptapEditor | null;
	npcLibrary: NpcLibrary | null;
	pollAvailable: boolean;
	onTextColorClick: () => void;
	onLinkClick: () => void;
	onSearchAndReplaceClick: () => void;
	isSearchAndReplaceOpen: boolean;
	searchAndReplaceButtonRef: React.RefObject<HTMLButtonElement | null>;
	isMobile: boolean;
}) => {
	return (
		<>
			{/* Row 1: structure and inserts. Groups are divided by CSS borders that
			    hide themselves at a wrap point (see toolbar.scss). */}
			<div className="tiptap-toolbar-row">
				<ToolbarGroup>
					<UndoRedoButton action="undo" />
					<UndoRedoButton action="redo" />
				</ToolbarGroup>

				<ToolbarGroup>
					<HeadingDropdownMenu modal={false} levels={[1, 2, 3, 4]} />
					<ListDropdownMenu
						modal={false}
						types={["bulletList", "orderedList", "taskList"]}
					/>
					<BlockquoteButton />
					<QuoteButton editor={editor} />
					<OocButton editor={editor} />
					<SpoilerButton editor={editor} />
					<CodeBlockButton />
					<OrderedListOptions />
				</ToolbarGroup>

				<ToolbarGroup>
					{!isMobile ? <LinkPopover /> : <LinkButton onClick={onLinkClick} />}
					<ImageUrlButton editor={editor} />
					<YoutubePopover editor={editor} />
					<HorizontalRuleButton editor={editor} />
					<NoteButton editor={editor} />
					<BoxDropdown editor={editor} />
					<TableDropdown editor={editor} />
					<ColumnsDropdown editor={editor} />
					<ImageFloatDropdown editor={editor} />
					<ImageLinkPopover editor={editor} />
					{pollAvailable && <PollButton editor={editor} />}
					{npcLibrary && <NpcSpeakerButton editor={editor} library={npcLibrary} />}
					{npcLibrary && <NpcRosterButton editor={editor} />}
				</ToolbarGroup>

				<ToolbarGroup className="tiptap-toolbar-group--end">
					<SearchAndReplaceButton
						ref={searchAndReplaceButtonRef}
						aria-expanded={isSearchAndReplaceOpen}
						data-active-state={isSearchAndReplaceOpen ? "on" : "off"}
						onClick={onSearchAndReplaceClick}
					/>
				</ToolbarGroup>
			</div>

			{/* Row 2: text formatting. */}
			<div className="tiptap-toolbar-row">
				<ToolbarGroup>
					<MarkButton type="bold" />
					<MarkButton type="italic" />
					<MarkButton type="strike" />
					<MarkButton type="code" />
					<MarkButton type="underline" />
					<MarkButton type="superscript" />
					<MarkButton type="subscript" />
				</ToolbarGroup>

				<ToolbarGroup>
					{!isMobile ? (
						<TextColorPopover />
					) : (
						<TextColorPopoverButton onClick={onTextColorClick} />
					)}
					<HighlightPopover />
				</ToolbarGroup>

				<ToolbarGroup>
					<FontSizeDropdown />
					<FontFamilyDropdown />
				</ToolbarGroup>

				<ToolbarGroup>
					<TextAlignButton align="left" />
					<TextAlignButton align="center" />
					<TextAlignButton align="right" />
					<TextAlignButton align="justify" />
				</ToolbarGroup>
			</div>
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
	<div className="tiptap-toolbar-row">
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

		{type === "color" ? <TextColorPopoverContent onDone={onBack} /> : <LinkContent />}
	</div>
);

type EditorProps = {
	id?: string;
	value: JSONContent | null | undefined;
	onChange: (value: JSONContent) => void;
	onBlur?: () => void;
	className?: string;
	/** Forwarded to the editable element as `aria-labelledby`. */
	ariaLabelledBy?: string;
	/**
	 * The quick NPC library speech blocks may name. Only when set does the toolbar
	 * get an NPC button and a block's speaker become changeable; leave it unset for
	 * editors that have no NPCs to offer.
	 */
	npcLibrary?: NpcLibrary | null;
	/**
	 * The edited post's own `content_npcs`, so a block whose NPC has since left the
	 * library still shows its name and image.
	 */
	contentNpcs?: readonly ContentNpc[];
	/**
	 * The edited post's own `content_mentions`, so a mention in an old post shows
	 * its user's current name.
	 */
	contentMentions?: readonly ContentMention[];
	/**
	 * Whether `@` opens a user picker and the document may hold mention nodes. Only
	 * for post editors: the API validates mentions on posts alone.
	 */
	mentions?: boolean;
	/**
	 * Whether the toolbar offers a Poll button, which marks where the thread's poll
	 * appears in the post. Only for the first post of a thread that has (or is getting)
	 * a poll.
	 */
	pollAvailable?: boolean;
};

const NO_CONTENT_NPCS: readonly ContentNpc[] = [];
const NO_CONTENT_MENTIONS: readonly ContentMention[] = [];

const Editor = ({
	id,
	value,
	onChange,
	onBlur,
	className,
	ariaLabelledBy,
	npcLibrary = null,
	contentNpcs = NO_CONTENT_NPCS,
	contentMentions = NO_CONTENT_MENTIONS,
	mentions = false,
	pollAvailable = false,
}: EditorProps) => {
	// Users picked since the editor opened, whom the post's own lookup doesn't list.
	const [pickedMentions, setPickedMentions] = useState<ContentMention[]>([]);
	const mentionPicker = useMentionPicker((user) =>
		setPickedMentions((picked) => addMentions(picked, [user])),
	);
	const isMobile = useIsBreakpoint();
	const { height } = useWindowSize();
	const [mobileView, setMobileView] = useState<"main" | "color" | "link">("main");
	const [isSearchAndReplaceOpen, setIsSearchAndReplaceOpen] = useState(false);
	const toolbarRef = useRef<HTMLDivElement>(null);
	const wrapperRef = useRef<HTMLDivElement>(null);
	const searchAndReplaceButtonRef = useRef<HTMLButtonElement>(null);

	const editor = useEditor({
		immediatelyRender: false,
		extensions: [
			StarterKit.configure({
				heading: false,
				horizontalRule: false,
				hardBreak: false,
				link: false,
				orderedList: false,
			}),
			SafeOrderedList,
			BannerHeading,
			NonInclusiveLink.configure({
				openOnClick: false,
				enableClickSelection: false,
				isAllowedUri: isAllowedLinkUri,
			}),
			HorizontalRule,
			Note,
			NpcSpeaker,
			NpcRoster,
			Quote,
			Spoiler,
			Youtube,
			Poll,
			Box,
			Columns,
			Column,
			...TABLE_EXTENSIONS,
			...(mentions
				? [Mention.configure({ suggestion: mentionPicker.suggestion })]
				: []),
			TextAlign.configure({ types: ["heading", "paragraph"] }),
			TaskList,
			TaskItem.configure({ nested: true }),
			TextStyle,
			Color,
			SafeHighlight,
			FontSize,
			FontFamily,
			FloatImage,
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
			if (editor.isEmpty && editor.state.selection instanceof AllSelection) {
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
				...(ariaLabelledBy ? { "aria-labelledby": ariaLabelledBy } : {}),
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

	// The toolbar wraps onto more lines as the editor narrows, so the search panel
	// (which hangs below it) reads the toolbar's real height from a CSS variable.
	useEffect(() => {
		const toolbar = toolbarRef.current;
		const wrapper = wrapperRef.current;
		if (!toolbar || !wrapper) return;
		const observer = new ResizeObserver(() => {
			wrapper.style.setProperty(
				"--editor-toolbar-height",
				`${toolbar.getBoundingClientRect().height}px`,
			);
		});
		observer.observe(toolbar);
		return () => observer.disconnect();
	}, []);

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
			// setContent doesn't remap the old selection onto the new doc in a
			// useful way — left alone it can resolve to an AllSelection or a
			// NodeSelection wrapping an isolating node (e.g. Quote) rather than a
			// normal text cursor, which breaks click-to-place and arrow-key
			// navigation until the user manually reselects. Put the cursor at a
			// definite, normal spot instead.
			editor.commands.setTextSelection(editor.state.doc.content.size);
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
	const speakerContext = { library: npcLibrary, fallback: contentNpcs };
	// A note's recipient picked in this editor gets a name before the post is saved,
	// the same way a picked @mention does.
	const noteContext = {
		remember: (user: SearchUser) =>
			setPickedMentions((picked) => addMentions(picked, [user])),
	};

	return (
		<div ref={wrapperRef} className="tiptap-editor simple-editor-wrapper">
			<EditorContext.Provider value={providerValue}>
				<Toolbar
					ref={toolbarRef}
					className="tiptap-toolbar--stacked"
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
							npcLibrary={npcLibrary}
							pollAvailable={pollAvailable}
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

				{/* The speech blocks' node views render under EditorContent, so they
				    read the library from here. */}
				<NpcSpeakerContext.Provider value={speakerContext}>
					<MentionContext.Provider
						value={findMentionNames(pickedMentions, contentMentions)}
					>
						<NoteContext.Provider value={noteContext}>
							<EditorContent
								editor={editor}
								role="presentation"
								className={clsx("simple-editor-content", className)}
							/>
						</NoteContext.Provider>
					</MentionContext.Provider>
				</NpcSpeakerContext.Provider>
				{mentions && mentionPicker.popup}
			</EditorContext.Provider>
		</div>
	);
};

export default Editor;
