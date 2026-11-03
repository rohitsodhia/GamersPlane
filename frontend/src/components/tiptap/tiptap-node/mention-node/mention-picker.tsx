import { useQuery } from "@tanstack/react-query";
import type { SuggestionOptions } from "@tiptap/suggestion";
import { type RefObject, useEffect, useRef, useState } from "react";
import { DEBOUNCE_MS, MIN_USER_SEARCH_LENGTH } from "#/lib/constants";
import { type SearchUser, usersAutocompleteQueryOptions } from "#/queries/users";
import { stepIndex } from "./mention";
import styles from "./mention-picker.module.css";

type KeyHandler = (event: KeyboardEvent) => boolean;

type PickerState = {
	query: string;
	rect: DOMRect | null;
	// Inserts the mention for the user into the editor.
	pick: (user: SearchUser) => void;
};

/**
 * The editor's `@` picker. Pass `suggestion` to the Mention extension and render
 * `popup` beside the editor (it needs the app's QueryClient, so it can't live in
 * Tiptap's own renderer). `remember` is told of each picked user so the editor can
 * show their name before the post is saved.
 */
export function useMentionPicker(remember: (user: SearchUser) => void) {
	const [state, setState] = useState<PickerState | null>(null);
	const keyHandler = useRef<KeyHandler | null>(null);
	const [suggestion] = useState<Omit<SuggestionOptions, "editor">>(() => {
		const show = (props: {
			query: string;
			clientRect?: (() => DOMRect | null) | null;
			command: (user: SearchUser) => void;
		}) =>
			setState({
				query: props.query,
				rect: props.clientRect?.() ?? null,
				pick: (user) => {
					remember(user);
					props.command(user);
				},
			});

		return {
			char: "@",
			allowSpaces: false,
			items: () => [],
			command: ({ editor, range, props }) => {
				editor
					.chain()
					.focus()
					.insertContentAt(range, [
						{ type: "mention", attrs: { userId: (props as SearchUser).id } },
						{ type: "text", text: " " },
					])
					.run();
			},
			render: () => ({
				onStart: show,
				onUpdate: show,
				onKeyDown: ({ event }) => keyHandler.current?.(event) ?? false,
				onExit: () => setState(null),
			}),
		};
	});

	return {
		suggestion,
		popup: state && <MentionPicker state={state} keyHandler={keyHandler} />,
	};
}

function MentionPicker({
	state,
	keyHandler,
}: {
	state: PickerState;
	keyHandler: RefObject<KeyHandler | null>;
}) {
	const [debounced, setDebounced] = useState(state.query);
	const [selected, setSelected] = useState(0);

	useEffect(() => {
		const timer = setTimeout(() => setDebounced(state.query), DEBOUNCE_MS);
		return () => clearTimeout(timer);
	}, [state.query]);

	// Judged on the live text, so deleting back under the minimum clears the list
	// at once instead of after the debounce.
	const tooShort = state.query.length < MIN_USER_SEARCH_LENGTH;
	const { data, isError, isPending } = useQuery({
		...usersAutocompleteQueryOptions(debounced),
		enabled: !tooShort && debounced.length >= MIN_USER_SEARCH_LENGTH,
	});
	const users = tooShort ? [] : (data ?? []);
	const active = Math.min(selected, Math.max(users.length - 1, 0));

	// Re-bound each render so it sees the current results and selection.
	useEffect(() => {
		keyHandler.current = (event) => {
			if (event.key === "ArrowDown" || event.key === "ArrowUp") {
				setSelected(
					stepIndex(active, event.key === "ArrowDown" ? 1 : -1, users.length),
				);
				return true;
			}
			if ((event.key === "Enter" || event.key === "Tab") && users[active]) {
				state.pick(users[active]);
				return true;
			}
			return false;
		};
		return () => {
			keyHandler.current = null;
		};
	});

	if (!state.rect) return null;

	return (
		<ul
			className={styles["picker"]}
			aria-label="Mention a user"
			style={{ left: state.rect.left, top: state.rect.bottom + 4 }}
		>
			{users.map((user, index) => (
				<li key={user.id}>
					{/* Not focusable: the editor keeps focus and takes the arrow keys. */}
					<button
						type="button"
						tabIndex={-1}
						aria-current={index === active}
						className={styles["option"]}
						// Keeps the editor focused, so the click doesn't end the suggestion.
						onMouseDown={(event) => event.preventDefault()}
						// Move, not enter: arrow-key scrolling slides options under a still
						// pointer, which shouldn't steal the keyboard's choice.
						onMouseMove={() => setSelected(index)}
						onClick={() => state.pick(user)}
					>
						{user.username}
					</button>
				</li>
			))}
			{users.length === 0 && (
				<li className={styles["empty"]} aria-live="polite">
					{tooShort
						? `Type at least ${MIN_USER_SEARCH_LENGTH} letters`
						: isError
							? "Couldn't search users"
							: isPending
								? "Searching…"
								: "No matches"}
				</li>
			)}
		</ul>
	);
}
