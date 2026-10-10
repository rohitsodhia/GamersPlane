import { Link } from "@tanstack/react-router";
import { Select } from "#/components/Select";
import type { PostableCharacter } from "#/queries/forums";
import { postAsId, postAsKey, postAsOptions } from "./-post-as";
import styles from "./-post-as-picker.module.css";

// Which character to post as. Renders nothing when there are none to pick from
// (and no current one to show).
export function PostAsPicker({
	id,
	characters,
	viewerId,
	value,
	onChange,
	current = null,
}: {
	id: string;
	characters: PostableCharacter[];
	viewerId: number | undefined;
	value: number | null;
	onChange: (id: number | null) => void;
	// The post's existing character, kept as an option even if it's no longer listed.
	current?: { id: number; name: string } | null;
}) {
	if (characters.length === 0 && !current) return null;
	const options = postAsOptions(characters, viewerId, current);
	const selected = characters.find((character) => character.id === value);
	const selectedName = selected?.name ?? (current?.id === value ? current.name : null);

	return (
		<div className={styles["post-as"]}>
			<Select
				id={id}
				items={options}
				getId={(option) => option.key}
				getLabel={(option) => option.label}
				selectedId={postAsKey(value)}
				onChange={(key) => onChange(postAsId(key))}
			/>
			{value !== null && selectedName !== null && (
				<Link
					to="/characters/$characterId"
					params={{ characterId: value }}
					target="_blank"
					rel="noreferrer"
				>
					{selectedName}
				</Link>
			)}
		</div>
	);
}
