import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { Autocomplete } from "#/components/Autocomplete";
import { DEBOUNCE_MS, MIN_USER_SEARCH_LENGTH } from "#/lib/constants";
import { type SearchUser, usersAutocompleteQueryOptions } from "#/queries/users";

// Adds users to a note's recipients: the mention picker's user search, as a field
// that empties after each pick so the next recipient can be typed straight away.
// `exclude` drops users the note already names.
export function NoteRecipientPicker({
	onPick,
	exclude,
}: {
	onPick: (user: SearchUser) => void;
	exclude: readonly number[];
}) {
	const id = useId();
	const [inputValue, setInputValue] = useState("");
	const [debounced, setDebounced] = useState("");

	useEffect(() => {
		const timer = setTimeout(() => setDebounced(inputValue.trim()), DEBOUNCE_MS);
		return () => clearTimeout(timer);
	}, [inputValue]);

	const enabled =
		inputValue.trim().length >= MIN_USER_SEARCH_LENGTH &&
		debounced.length >= MIN_USER_SEARCH_LENGTH;
	const { data } = useQuery({ ...usersAutocompleteQueryOptions(debounced), enabled });
	const users = enabled
		? (data ?? []).filter((user) => !exclude.includes(user.id))
		: [];

	return (
		<Autocomplete
			id={id}
			name="note_recipient"
			noPasswordManager
			className="note-node-recipient-picker"
			inputValue={inputValue}
			onInputChange={setInputValue}
			items={users}
			getId={(user) => String(user.id)}
			getLabel={(user) => user.username}
			placeholder="Add a user..."
			onAction={(id, { clear }) => {
				const picked = users.find((user) => String(user.id) === id);
				if (picked) onPick(picked);
				clear();
			}}
		/>
	);
}
