import { useQuery } from "@tanstack/react-query";
import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewContent,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import { createContext, useContext, useRef, useState } from "react";
import { NpcChooser } from "#/components/NpcChooser";
import {
	type ContentNpc,
	type NpcLibrary,
	npcsQueryOptions,
} from "#/queries/quick-npcs";
import {
	findSpeaker,
	initialOf,
	type SpeakerDisplay,
	type SpeakerLookup,
	speakerFor,
} from "./npc-speaker";

export interface NpcSpeakerOptions {
	HTMLAttributes: Record<string, unknown>;
	// Read-only rendering (`generateHTML`): the NPCs the document's blocks name, by
	// id. The document itself only ever holds the id.
	npcs: SpeakerLookup;
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		npcSpeaker: {
			/**
			 * Wrap the current selection (or insert at the cursor) in a speech
			 * block spoken by the quick NPC with this id.
			 */
			setNpcSpeaker: (attributes: { npcId: number }) => ReturnType;
		};
	}
}

// What the editable node view needs from the surrounding Editor: the library its
// NPCs come from (null when the editor can't pick any) and, for editing an old
// post, its own `content_npcs` to fall back on for NPCs the library no longer lists.
export type NpcSpeakerContextValue = {
	library: NpcLibrary | null;
	fallback: readonly ContentNpc[];
};

export const NpcSpeakerContext = createContext<NpcSpeakerContextValue>({
	library: null,
	fallback: [],
});

function NpcSpeakerView({ node, updateAttributes, deleteNode, editor }: NodeViewProps) {
	const { library, fallback } = useContext(NpcSpeakerContext);
	const [isChoosing, setIsChoosing] = useState(false);
	const nameRef = useRef<HTMLButtonElement>(null);
	const { data: listed = [] } = useQuery({
		...npcsQueryOptions(library ?? { kind: "me" }),
		enabled: library !== null,
	});
	const npcId: unknown = node.attrs.npcId;
	const speaker: SpeakerDisplay = findSpeaker(npcId, listed, fallback);
	const canChange = editor.isEditable && library !== null;

	return (
		<NodeViewWrapper className="npc-speaker" data-type="npcSpeaker">
			<div className="npc-speaker-avatar" contentEditable={false}>
				{speaker.image ? (
					<img src={speaker.image.url} alt="" />
				) : (
					<span>{initialOf(speaker.name)}</span>
				)}
			</div>
			<div className="npc-speaker-bubble">
				<div className="npc-speaker-name" contentEditable={false}>
					{canChange ? (
						// A plain button, as in the note node: the node view lives inside
						// ProseMirror, which is wary of pointer events it didn't expect.
						<button
							ref={nameRef}
							type="button"
							className="npc-speaker-name-button"
							aria-label={`Speaker: ${speaker.name}. Change`}
							aria-haspopup="dialog"
							onClick={() => setIsChoosing(true)}
						>
							{speaker.name}
						</button>
					) : (
						<span>{speaker.name}</span>
					)}
					{editor.isEditable && (
						<button
							type="button"
							className="npc-speaker-delete"
							aria-label="Delete speech block"
							onClick={deleteNode}
						>
							&times;
						</button>
					)}
				</div>
				<NodeViewContent className="npc-speaker-content" />
			</div>
			{canChange && library !== null && (
				<NpcChooser
					library={library}
					isOpen={isChoosing}
					onOpenChange={setIsChoosing}
					triggerRef={nameRef}
					onChoose={(npc) => updateAttributes({ npcId: npc.id })}
				/>
			)}
		</NodeViewWrapper>
	);
}

// A container block holding speech by one quick NPC, shown as its own bubble with
// the NPC's avatar beside it, so a post can hold a dialogue. Only the NPC's id is
// stored: its name and image are looked up when the post is shown, so renaming or
// re-imaging an NPC changes its old posts too (and a deleted one still renders).
export const NpcSpeaker = Node.create<NpcSpeakerOptions>({
	name: "npcSpeaker",
	group: "block",
	content: "block+",
	defining: true,
	isolating: true,

	addOptions() {
		return {
			HTMLAttributes: {},
			npcs: {},
		};
	},

	addAttributes() {
		return {
			npcId: {
				default: null,
				parseHTML: (element) => {
					const id = Number(element.getAttribute("data-npc-id"));
					return Number.isInteger(id) && id > 0 ? id : null;
				},
				renderHTML: (attributes) =>
					typeof attributes.npcId === "number"
						? { "data-npc-id": String(attributes.npcId) }
						: {},
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: `div[data-type="${this.name}"]`,
				// The avatar and name aren't document content.
				contentElement: ".npc-speaker-content",
			},
		];
	},

	renderHTML({ node, HTMLAttributes }) {
		const speaker = speakerFor(node.attrs.npcId, this.options.npcs);

		return [
			"div",
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
				"data-type": this.name,
				class: "npc-speaker",
			}),
			[
				"div",
				{ class: "npc-speaker-avatar" },
				speaker.image
					? ["img", { src: speaker.image.url, alt: "" }]
					: ["span", initialOf(speaker.name)],
			],
			[
				"div",
				{ class: "npc-speaker-bubble" },
				["div", { class: "npc-speaker-name" }, ["span", speaker.name]],
				["div", { class: "npc-speaker-content" }, 0],
			],
		];
	},

	addNodeView() {
		return ReactNodeViewRenderer(NpcSpeakerView);
	},

	addCommands() {
		return {
			setNpcSpeaker:
				(attributes) =>
				({ commands, state }) => {
					if (state.selection.empty) {
						return commands.insertContent({
							type: this.name,
							attrs: attributes,
							content: [{ type: "paragraph" }],
						});
					}
					return commands.wrapIn(this.name, attributes);
				},
		};
	},
});

export default NpcSpeaker;
