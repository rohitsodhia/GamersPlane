import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type RefObject, useState } from "react";
import {
	Dialog,
	Input,
	Label,
	ListBox,
	ListBoxItem,
	Popover,
	SearchField,
} from "react-aria-components";
import { filterSpeakers } from "#/components/tiptap/tiptap-node/npc-speaker-node/npc-speaker";
import {
	type NpcLibrary,
	npcsQueryKey,
	npcsQueryOptions,
	type QuickNpc,
} from "#/queries/quick-npcs";
import styles from "./NpcChooser.module.css";
import { QuickNpcModal } from "./QuickNpcModal";

const NEW_ID = "new";
const NO_IDS: readonly number[] = [];

// Picks a quick NPC for a speech block or a roster: the library's NPCs
// (searchable) and a "New quick NPC" entry that opens the creation modal. It floats
// over the element it's opened from, and the modal is kept outside the popover so it
// outlives the popover closing. Both portal out of the form the editor sits in,
// but React still bubbles their events to it, so nothing here lets Enter submit.
// `excludeIds` hides NPCs that can't be picked (those already in a roster).
export function NpcChooser({
	library,
	isOpen,
	onOpenChange,
	triggerRef,
	onChoose,
	excludeIds = NO_IDS,
}: {
	library: NpcLibrary;
	isOpen: boolean;
	onOpenChange: (isOpen: boolean) => void;
	triggerRef: RefObject<Element | null>;
	onChoose: (npc: QuickNpc) => void;
	excludeIds?: readonly number[];
}) {
	const queryClient = useQueryClient();
	// The name typed into the search box when "New quick NPC" was chosen.
	const [newName, setNewName] = useState<string | null>(null);

	return (
		<>
			<Popover
				triggerRef={triggerRef}
				isOpen={isOpen}
				onOpenChange={onOpenChange}
				placement="bottom start"
				className={`react-aria-Popover ${styles["popover"]}`}
			>
				<Dialog aria-label="Choose a quick NPC" className={styles["dialog"]}>
					<ChooserBody
						library={library}
						excludeIds={excludeIds}
						onChoose={(npc) => {
							onChoose(npc);
							onOpenChange(false);
						}}
						onNew={(name) => {
							setNewName(name);
							onOpenChange(false);
						}}
					/>
				</Dialog>
			</Popover>
			<QuickNpcModal
				library={library}
				isOpen={newName !== null}
				onOpenChange={(open) => {
					if (!open) setNewName(null);
				}}
				initialName={newName ?? ""}
				onCreated={(created) => {
					// Show it in the block straight away, before the list refetches.
					queryClient.setQueryData<QuickNpc[]>(npcsQueryKey(library), (old) =>
						old?.some((npc) => npc.id === created.id) ? old : [created, ...(old ?? [])],
					);
					onChoose(created);
				}}
			/>
		</>
	);
}

// Mounted only while the popover is open, so each opening starts with a clear search.
function ChooserBody({
	library,
	excludeIds,
	onChoose,
	onNew,
}: {
	library: NpcLibrary;
	excludeIds: readonly number[];
	onChoose: (npc: QuickNpc) => void;
	onNew: (name: string) => void;
}) {
	const [query, setQuery] = useState("");
	const { data: npcs, isPending, isError } = useQuery(npcsQueryOptions(library));

	const matches = filterSpeakers(
		(npcs ?? []).filter((npc) => !excludeIds.includes(npc.id)),
		query,
	);
	const typed = query.trim();
	// The "new" entry leads the list; the rest are the library's matches.
	const items: { id: string; npc: QuickNpc | null }[] = [
		{ id: NEW_ID, npc: null },
		...matches.map((npc) => ({ id: String(npc.id), npc })),
	];

	const choose = (key: string | number) => {
		const picked = items.find((item) => item.id === String(key));
		if (!picked) return;
		if (picked.npc) onChoose(picked.npc);
		else onNew(typed);
	};

	return (
		<div className={styles["body"]}>
			<SearchField
				className={styles["search"]}
				value={query}
				onChange={setQuery}
				autoFocus
			>
				<Label className="visually-hidden">Search quick NPCs</Label>
				<Input
					placeholder="Search, or type a new name"
					onKeyDown={(event) => {
						// The editor sits inside the post form, where Enter would submit it.
						if (event.key === "Enter") {
							event.preventDefault();
							if (matches[0]) onChoose(matches[0]);
							else if (typed !== "") onNew(typed);
						}
					}}
				/>
			</SearchField>
			{isPending && <div className={styles["status"]}>Loading...</div>}
			{isError && (
				<div className={styles["status"]} role="alert">
					Couldn't load the quick NPCs.
				</div>
			)}
			{!isPending && !isError && (
				<ListBox
					aria-label="Quick NPCs"
					className={styles["list"]}
					items={items}
					dependencies={[typed]}
					onAction={choose}
				>
					{(item) =>
						item.npc ? (
							<ListBoxItem
								id={item.id}
								textValue={item.npc.name}
								className={styles["row"]}
							>
								<NpcThumb npc={item.npc} />
								<span className={styles["name"]}>{item.npc.name}</span>
							</ListBoxItem>
						) : (
							<ListBoxItem
								id={item.id}
								textValue="New quick NPC"
								className={styles["row"]}
							>
								<span className={styles["name"]}>
									{typed === "" ? "New quick NPC..." : `New quick NPC: ${typed}`}
								</span>
							</ListBoxItem>
						)
					}
				</ListBox>
			)}
		</div>
	);
}

function NpcThumb({ npc }: { npc: QuickNpc }) {
	return npc.image ? (
		<img className={styles["thumb"]} src={npc.image.url} alt="" />
	) : (
		<span className={styles["thumb"]} aria-hidden="true" />
	);
}
