import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import {
	GridList,
	GridListItem,
	Input,
	Label,
	SearchField,
	ToggleButton,
	ToggleButtonGroup,
} from "react-aria-components";
import { NpcImageChooser } from "#/components/NpcImageChooser";
import type { PostableCharacter } from "#/queries/forums";
import { type GameNpc, gameImagesQueryOptions } from "#/queries/game";
import type { MeResponse } from "#/queries/me";
import type { PostedNpc } from "#/queries/posts";
import {
	type CharacterType,
	effectiveAvatarId,
	entriesOfType,
	isEntrySelected,
	modeOf,
	type NpcEntry,
	newNpcEntry,
	npcImageUrl,
	orderEntries,
	PLAYER,
	type PostAsValue,
	pickAvatar,
	pickEntry,
	resolveNpc,
	selectOnOpen,
	showsFilter,
	visibleTypes,
} from "./-post-as";
import styles from "./-post-as-picker.module.css";

// Which character (and avatar) or quick NPC to post as. A bar shows the current
// choice; the PC / NPC buttons open a scrollable list of that type to pick from.
// Renders nothing when there is nobody to pick from (and no current one to show).
export function PostAsPicker({
	labelId,
	characters,
	npcs = [],
	npcGameId = null,
	viewer,
	value,
	onChange,
	current = null,
	currentNpc = null,
}: {
	// The visible "Post as" label's id, naming the buttons.
	labelId: string;
	characters: PostableCharacter[];
	// The game's quick NPCs (only a GM's response has any).
	npcs?: GameNpc[];
	// Set when the viewer can make quick NPCs: the game whose image library they use.
	npcGameId?: number | null;
	viewer: Pick<MeResponse, "id" | "username" | "avatar"> | undefined;
	value: PostAsValue;
	onChange: (value: PostAsValue) => void;
	// The post's existing character, shown in the bar even if it's no longer listed.
	current?: { id: number; name: string; avatar: string | null } | null;
	// The same for the post's existing quick NPC.
	currentNpc?: PostedNpc | null;
}) {
	const [expanded, setExpanded] = useState<CharacterType | null>(null);
	const [query, setQuery] = useState("");
	const canCreateNpc = npcGameId !== null;
	const { data: images = [] } = useQuery({
		...gameImagesQueryOptions(npcGameId ?? 0),
		enabled: canCreateNpc && value.npc !== undefined,
	});

	if (
		characters.length === 0 &&
		npcs.length === 0 &&
		!canCreateNpc &&
		!current &&
		!currentNpc
	) {
		return null;
	}

	const types = visibleTypes(characters, npcs, canCreateNpc);
	const mode = modeOf(value, characters);
	const lit =
		mode === "player" || types.some(({ type }) => type === mode) ? mode : null;
	const selected = value.npc
		? undefined
		: characters.find((character) => character.id === value.characterId);
	const npc = value.npc ? resolveNpc(value.npc, npcs) : null;
	const shown: PostAsValue = npc ? { characterId: null, avatarId: null, npc } : value;

	let barName = viewer?.username ?? "Player";
	let barAvatar: string | null = viewer?.avatar ?? null;
	if (npc) {
		barName = npc.name;
		barAvatar = npcImageUrl(npc, images, npcs, currentNpc);
	} else if (selected) {
		barName = selected.name;
		const avatarId = effectiveAvatarId(selected, value.avatarId);
		barAvatar = selected.avatars.find((a) => a.id === avatarId)?.url ?? null;
	} else if (value.characterId !== null && current?.id === value.characterId) {
		barName = current.name;
		barAvatar = current.avatar;
	}

	const isNpcList = expanded === "npc";
	const entries = expanded === null ? [] : entriesOfType(characters, npcs, expanded);
	const ordered = orderEntries(entries, query);
	const newEntry = isNpcList && canCreateNpc ? newNpcEntry(query, npcs, shown) : null;
	// The new-NPC row leads the list, ahead of the recents and their divider.
	const items = newEntry ? [newEntry, ...ordered.items] : ordered.items;
	const recentCount = ordered.recentCount;
	const afterRecents = newEntry ? recentCount + 1 : recentCount;
	const firstAfterDivider =
		recentCount > 0 && afterRecents < items.length ? items[afterRecents].key : null;
	const showList =
		expanded !== null && (entries.length > 0 || (isNpcList && canCreateNpc));

	const pickEntryByKey = (key: string | number | undefined) => {
		const picked = items.find((entry) => entry.key === String(key));
		if (picked && !isEntrySelected(picked, shown)) onChange(pickEntry(picked));
	};

	return (
		<div className={styles["post-as"]}>
			<div className={styles["bar"]}>
				{barAvatar && <img className={styles["bar-avatar"]} src={barAvatar} alt="" />}
				{value.characterId === null ? (
					<span>{barName}</span>
				) : (
					<Link
						to="/characters/$characterId"
						params={{ characterId: value.characterId }}
						target="_blank"
						rel="noreferrer"
					>
						{barName}
					</Link>
				)}
				<ToggleButtonGroup
					aria-labelledby={labelId}
					className={styles["modes"]}
					selectionMode="single"
					selectedKeys={lit === null ? [] : [lit]}
					onSelectionChange={(keys) => {
						const [key] = [...keys];
						// Pressing the lit button toggles its list.
						if (key === undefined) {
							if (mode === "pc" || mode === "npc") {
								setExpanded(expanded === mode ? null : mode);
								setQuery("");
							}
							return;
						}
						if (key === "player") {
							onChange(PLAYER);
							setExpanded(null);
							return;
						}
						const type = key as CharacterType;
						const picked = selectOnOpen(characters, type, value, npcs);
						if (picked) onChange(picked);
						// A GM's empty NPC list has nothing to pick, so the button isn't lit
						// and a second press has to close the list.
						setExpanded(!picked && expanded === type && mode !== type ? null : type);
						setQuery("");
					}}
				>
					<ToggleButton id="player" className={styles["mode"]}>
						Player
					</ToggleButton>
					{types.map(({ type, label }) => (
						<ToggleButton key={type} id={type} className={styles["mode"]}>
							{label}
						</ToggleButton>
					))}
				</ToggleButtonGroup>
			</div>

			{showList && (
				<div className={styles["list-area"]}>
					{showsFilter(entries, isNpcList && canCreateNpc) && (
						<SearchField className={styles["filter"]} value={query} onChange={setQuery}>
							<Label className={styles["filter-help"]}>
								{isNpcList && canCreateNpc
									? "Filter, or type a new NPC's name"
									: "Filter by name or owner"}
							</Label>
							<Input
								onKeyDown={(e) => {
									// Inside the post form, where Enter would submit the post.
									if (e.key === "Enter") {
										e.preventDefault();
										if (items[0]) pickEntryByKey(items[0].key);
									}
								}}
							/>
						</SearchField>
					)}
					<GridList
						aria-label={`${expanded === "pc" ? "PCs" : "NPCs"} to post as`}
						className={styles["list"]}
						layout="grid"
						items={items}
						dependencies={[value, firstAfterDivider]}
						selectionMode="single"
						disallowEmptySelection
						selectedKeys={items
							.filter((entry) => isEntrySelected(entry, shown))
							.map((entry) => entry.key)}
						renderEmptyState={() => (
							<div className={styles["empty"]}>
								{isNpcList && canCreateNpc
									? "Type a name to make a quick NPC"
									: "No matching characters"}
							</div>
						)}
						onSelectionChange={(keys) => pickEntryByKey([...keys][0])}
					>
						{(entry) => (
							<GridListItem
								id={entry.key}
								textValue={entryText(entry)}
								className={clsx(
									styles["row"],
									entry.key === firstAfterDivider && styles["after-divider"],
								)}
							>
								<EntryRow
									entry={entry}
									viewer={viewer}
									value={value}
									onChange={onChange}
								/>
							</GridListItem>
						)}
					</GridList>
				</div>
			)}

			{/* Only a new quick NPC picks its image here; an existing one's image is
			    changed from the game page's Quick NPCs list. */}
			{isNpcList && npcGameId !== null && npc && npc.id === null && (
				<div className={styles["npc-image"]}>
					<span>Image for {npc.name}:</span>
					<NpcImageChooser
						gameId={npcGameId}
						value={npc.imageId}
						onChange={(imageId) =>
							onChange({ characterId: null, avatarId: null, npc: { ...npc, imageId } })
						}
					/>
				</div>
			)}
		</div>
	);
}

function entryText(entry: NpcEntry): string {
	if (entry.kind === "character") return entry.character.name;
	if (entry.kind === "npc") return entry.npc.name;
	return `New quick NPC: ${entry.name}`;
}

function EntryRow({
	entry,
	viewer,
	value,
	onChange,
}: {
	entry: NpcEntry;
	viewer: Pick<MeResponse, "id" | "username" | "avatar"> | undefined;
	value: PostAsValue;
	onChange: (value: PostAsValue) => void;
}) {
	if (entry.kind === "new") {
		return <span className={styles["name"]}>New quick NPC: {entry.name}</span>;
	}
	if (entry.kind === "npc") {
		return (
			<>
				<span className={styles["name"]}>{entry.npc.name}</span>
				{entry.npc.image && (
					<span className={styles["thumbs"]}>
						<img className={styles["npc-thumb"]} src={entry.npc.image.url} alt="" />
					</span>
				)}
			</>
		);
	}
	const { character } = entry;
	return (
		<>
			<span className={styles["name"]}>
				{character.name}
				{character.owner.id !== viewer?.id && (
					<span className={styles["owner"]}> ({character.owner.username})</span>
				)}
			</span>
			{character.avatars.length > 0 && (
				<span className={styles["thumbs"]}>
					{character.avatars.map((avatar, index) => (
						<ToggleButton
							key={avatar.id}
							className={styles["thumb"]}
							aria-label={`${character.name} avatar ${index + 1}`}
							isSelected={
								effectiveAvatarId(
									character,
									character.id === value.characterId ? value.avatarId : null,
								) === avatar.id
							}
							onPress={() => onChange(pickAvatar(character, avatar.id))}
						>
							<img src={avatar.url} alt="" />
						</ToggleButton>
					))}
				</span>
			)}
		</>
	);
}
