import { Link } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import {
	GridList,
	GridListItem,
	Input,
	SearchField,
	ToggleButton,
	ToggleButtonGroup,
} from "react-aria-components";
import type { PostableCharacter } from "#/queries/forums";
import type { MeResponse } from "#/queries/me";
import {
	CHARACTER_TYPES,
	type CharacterType,
	charactersOfType,
	effectiveAvatarId,
	modeOf,
	orderCharacters,
	PLAYER,
	type PostAsValue,
	pickAvatar,
	pickCharacter,
	selectOnOpen,
	showsFilter,
} from "./-post-as";
import styles from "./-post-as-picker.module.css";

// Which character (and avatar) to post as. A bar shows the current choice; the
// PC / NPC buttons open a scrollable list of that type to pick from. Renders
// nothing when there are no characters to pick from (and no current one to show).
export function PostAsPicker({
	labelId,
	characters,
	viewer,
	value,
	onChange,
	current = null,
}: {
	// The visible "Post as" label's id, naming the buttons.
	labelId: string;
	characters: PostableCharacter[];
	viewer: Pick<MeResponse, "id" | "username" | "avatar"> | undefined;
	value: PostAsValue;
	onChange: (value: PostAsValue) => void;
	// The post's existing character, shown in the bar even if it's no longer listed.
	current?: { id: number; name: string; avatar: string | null } | null;
}) {
	const [expanded, setExpanded] = useState<CharacterType | null>(null);
	const [query, setQuery] = useState("");

	if (characters.length === 0 && !current) return null;

	const types = CHARACTER_TYPES.filter(
		({ type }) => charactersOfType(characters, type).length > 0,
	);
	const mode = modeOf(value, characters);
	const selected = characters.find((character) => character.id === value.characterId);

	let barName = viewer?.username ?? "Player";
	let barAvatar: string | null = viewer?.avatar ?? null;
	if (selected) {
		barName = selected.name;
		const avatarId = effectiveAvatarId(selected, value.avatarId);
		barAvatar = selected.avatars.find((a) => a.id === avatarId)?.url ?? null;
	} else if (value.characterId !== null && current?.id === value.characterId) {
		barName = current.name;
		barAvatar = current.avatar;
	}

	const ofType = expanded === null ? [] : charactersOfType(characters, expanded);
	const { items, recentCount } = orderCharacters(ofType, query);
	const firstAfterDivider =
		recentCount > 0 && recentCount < items.length ? items[recentCount].id : null;

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
					selectedKeys={mode === null ? [] : [mode]}
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
						const picked = selectOnOpen(characters, type, value);
						if (picked) onChange(picked);
						setExpanded(type);
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

			{expanded !== null && ofType.length > 0 && (
				<div className={styles["list-area"]}>
					{showsFilter(ofType) && (
						<SearchField
							aria-label="Filter characters"
							className={styles["filter"]}
							value={query}
							onChange={setQuery}
						>
							<Input placeholder="Filter by name or owner" />
						</SearchField>
					)}
					<GridList
						aria-label={`${expanded === "pc" ? "PCs" : "NPCs"} to post as`}
						className={styles["list"]}
						items={items}
						dependencies={[value, firstAfterDivider]}
						selectionMode="single"
						disallowEmptySelection
						selectedKeys={
							selected && selected.type === expanded ? [String(selected.id)] : []
						}
						renderEmptyState={() => (
							<div className={styles["empty"]}>No matching characters</div>
						)}
						onSelectionChange={(keys) => {
							const [key] = [...keys];
							const picked = items.find((c) => String(c.id) === String(key));
							if (picked && picked.id !== value.characterId)
								onChange(pickCharacter(picked));
						}}
					>
						{(character) => (
							<GridListItem
								id={String(character.id)}
								textValue={character.name}
								className={clsx(
									styles["row"],
									character.id === firstAfterDivider && styles["after-divider"],
								)}
							>
								<span className={styles["name"]}>
									{character.name}
									{character.owner.id !== viewer?.id && (
										<span className={styles["owner"]}>
											{" "}
											({character.owner.username})
										</span>
									)}
								</span>
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
							</GridListItem>
						)}
					</GridList>
				</div>
			)}
		</div>
	);
}
