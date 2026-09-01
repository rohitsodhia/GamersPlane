import { useRef, useState } from "react";
import { Autocomplete } from "#/components/Autocomplete";
import { DEBOUNCE_MS } from "#/lib/constants";
import { type SearchUser, searchUsers } from "#/queries/users";

export type UserRef = { username: string; id: number | null };

/**
 * Debounced username search backed by /users/autocomplete. Fills exactly one
 * user: type to search, then either click a result or type a username that
 * exactly matches one. The chosen username stays in the search box while its id
 * is reported alongside it; `id` is null until a match is confirmed. `exclude`
 * drops candidates that are already chosen elsewhere.
 */
export function UserAutocomplete({
	id,
	label,
	defaultUsername = "",
	onChange,
	exclude,
}: {
	id: string;
	label: string;
	defaultUsername?: string;
	onChange: (value: UserRef) => void;
	exclude?: (user: SearchUser) => boolean;
}) {
	const [inputValue, setInputValue] = useState(defaultUsername);
	const [results, setResults] = useState<SearchUser[]>([]);
	const searchTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	const select = (user: SearchUser) => {
		clearTimeout(searchTimer.current);
		setInputValue(user.username);
		setResults([]);
		onChange({ username: user.username, id: user.id });
	};

	const onInput = (value: string) => {
		setInputValue(value);
		clearTimeout(searchTimer.current);
		const query = value.trim();
		onChange({ username: query, id: null });
		if (!query) {
			setResults([]);
			return;
		}
		searchTimer.current = setTimeout(async () => {
			try {
				const users = await searchUsers(query);
				setResults(users);
				const exact = users.find(
					(user) => user.username.toLowerCase() === query.toLowerCase(),
				);
				if (exact) onChange({ username: exact.username, id: exact.id });
			} catch {
				setResults([]);
			}
		}, DEBOUNCE_MS);
	};

	const candidates = exclude ? results.filter((user) => !exclude(user)) : results;

	return (
		<div>
			<label htmlFor={id}>{label}</label>
			<Autocomplete
				id={id}
				inputValue={inputValue}
				items={candidates}
				getId={(user) => String(user.id)}
				getLabel={(user) => user.username}
				onInputChange={onInput}
				onAction={(pickedId) => {
					const picked = results.find((user) => String(user.id) === pickedId);
					if (picked) select(picked);
				}}
			/>
		</div>
	);
}
