import { useQuery } from "@tanstack/react-query";
import type { NodeViewProps } from "@tiptap/react";
import {
	mergeAttributes,
	Node,
	NodeViewWrapper,
	ReactNodeViewRenderer,
} from "@tiptap/react";
import { useContext, useRef, useState } from "react";
import { NpcChooser } from "#/components/NpcChooser";
import { npcsQueryOptions } from "#/queries/quick-npcs";
import {
	findSpeaker,
	initialOf,
	MAX_ROSTER_TITLE_LENGTH,
	rosterIds,
	type SpeakerLookup,
	speakerFor,
} from "../npc-speaker-node/npc-speaker";
import { NpcSpeakerContext } from "../npc-speaker-node/npc-speaker-node-extension";

export interface NpcRosterOptions {
	HTMLAttributes: Record<string, unknown>;
	// Read-only rendering (`generateHTML`): the NPCs the document's blocks name, by
	// id. The document itself only ever holds the ids.
	npcs: SpeakerLookup;
}

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		npcRoster: {
			/** Insert an empty roster (a titled grid of quick NPC portraits). */
			insertNpcRoster: () => ReturnType;
		};
	}
}

function NpcRosterView({ node, updateAttributes, deleteNode, editor }: NodeViewProps) {
	// The same library and fallback NPCs the speaker blocks use.
	const { library, fallback } = useContext(NpcSpeakerContext);
	const [isChoosing, setIsChoosing] = useState(false);
	const addRef = useRef<HTMLButtonElement>(null);
	const { data: listed = [] } = useQuery({
		...npcsQueryOptions(library ?? { kind: "me" }),
		enabled: library !== null,
	});
	const title: string = typeof node.attrs.title === "string" ? node.attrs.title : "";
	const ids = rosterIds(node.attrs.npcIds);
	const canEdit = editor.isEditable;

	return (
		<NodeViewWrapper className="npc-roster" data-type="npcRoster">
			<div className="npc-roster-header" contentEditable={false}>
				{canEdit ? (
					<input
						type="text"
						className="npc-roster-title-input"
						aria-label="Roster title"
						placeholder="Title (optional)"
						maxLength={MAX_ROSTER_TITLE_LENGTH}
						value={title}
						onChange={(event) => updateAttributes({ title: event.target.value })}
						onKeyDown={(event) => {
							// The editor sits inside the post form, where Enter would submit it.
							if (event.key === "Enter") event.preventDefault();
						}}
					/>
				) : (
					title !== "" && <div className="npc-roster-title">{title}</div>
				)}
				{canEdit && (
					<button
						type="button"
						className="npc-roster-delete"
						aria-label="Delete roster"
						onClick={deleteNode}
					>
						&times;
					</button>
				)}
			</div>
			<div className="npc-roster-grid" contentEditable={false}>
				{ids.map((id) => {
					const npc = findSpeaker(id, listed, fallback);
					return (
						<div className="npc-roster-tile" key={id}>
							<div className="npc-roster-portrait">
								{npc.image ? (
									<img src={npc.image.url} alt="" />
								) : (
									<span>{initialOf(npc.name)}</span>
								)}
								{canEdit && (
									<button
										type="button"
										className="npc-roster-remove"
										aria-label={`Remove ${npc.name} from the roster`}
										onClick={() =>
											updateAttributes({ npcIds: ids.filter((other) => other !== id) })
										}
									>
										&times;
									</button>
								)}
							</div>
							<div className="npc-roster-name">{npc.name}</div>
						</div>
					);
				})}
				{canEdit && library !== null && (
					<div className="npc-roster-tile">
						<button
							ref={addRef}
							type="button"
							className="npc-roster-portrait npc-roster-add"
							aria-label="Add NPC"
							aria-haspopup="dialog"
							onClick={() => setIsChoosing(true)}
						>
							<span>+</span>
						</button>
						<div className="npc-roster-name">Add NPC</div>
					</div>
				)}
			</div>
			{canEdit && ids.length === 0 && (
				<div className="npc-roster-hint" contentEditable={false}>
					A roster needs at least one NPC.
				</div>
			)}
			{canEdit && library !== null && (
				<NpcChooser
					library={library}
					isOpen={isChoosing}
					onOpenChange={setIsChoosing}
					triggerRef={addRef}
					excludeIds={ids}
					onChoose={(npc) => {
						if (ids.includes(npc.id)) return;
						updateAttributes({ npcIds: [...ids, npc.id] });
					}}
				/>
			)}
		</NodeViewWrapper>
	);
}

// A titled grid of quick NPC portraits with their names. Only the NPCs' ids (and
// the title) are stored: names and images are looked up when the post is shown,
// like the speaker block. Display only: the roster never edits an NPC.
export const NpcRoster = Node.create<NpcRosterOptions>({
	name: "npcRoster",
	group: "block",
	atom: true,
	selectable: true,

	addOptions() {
		return {
			HTMLAttributes: {},
			npcs: {},
		};
	},

	addAttributes() {
		return {
			title: {
				default: "",
				parseHTML: (element) => element.getAttribute("data-title") ?? "",
				renderHTML: (attributes) =>
					typeof attributes.title === "string" && attributes.title !== ""
						? { "data-title": attributes.title }
						: {},
			},
			npcIds: {
				default: [],
				parseHTML: (element) =>
					rosterIds(
						(element.getAttribute("data-npc-ids") ?? "")
							.split(",")
							.map((id) => Number(id)),
					),
				renderHTML: (attributes) => ({
					"data-npc-ids": rosterIds(attributes.npcIds).join(","),
				}),
			},
		};
	},

	parseHTML() {
		return [{ tag: `div[data-type="${this.name}"]` }];
	},

	renderHTML({ node, HTMLAttributes }) {
		const title: string = typeof node.attrs.title === "string" ? node.attrs.title : "";
		const tiles = rosterIds(node.attrs.npcIds).map((id) => {
			const npc = speakerFor(id, this.options.npcs);
			return [
				"div",
				{ class: "npc-roster-tile" },
				[
					"div",
					{ class: "npc-roster-portrait" },
					npc.image
						? ["img", { src: npc.image.url, alt: "" }]
						: ["span", initialOf(npc.name)],
				],
				["div", { class: "npc-roster-name" }, npc.name],
			];
		});

		return [
			"div",
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
				"data-type": this.name,
				class: "npc-roster",
			}),
			...(title !== "" ? [["div", { class: "npc-roster-title" }, title]] : []),
			["div", { class: "npc-roster-grid" }, ...tiles],
		];
	},

	addNodeView() {
		return ReactNodeViewRenderer(NpcRosterView);
	},

	addCommands() {
		return {
			insertNpcRoster:
				() =>
				({ commands }) =>
					commands.insertContent({
						type: this.name,
						attrs: { title: "", npcIds: [] },
					}),
		};
	},
});

export default NpcRoster;
