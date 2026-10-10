import clsx from "clsx";
import { useId } from "react";
import { Button, GridList, GridListItem, useDragAndDrop } from "react-aria-components";
import { Checkbox } from "#/components/Checkbox";
import { ConfirmDeleteButton } from "#/components/ConfirmDeleteButton";
import { Select } from "#/components/Select";
import styles from "./-poll-editor.module.css";
import {
	applyPaste,
	hasPollErrors,
	MAX_POLL_OPTIONS,
	MAX_POLL_TEXT_LENGTH,
	moveRows,
	newOptionRow,
	newPollState,
	type PollOptionRow,
	type PollState,
	pollErrors,
	removeOption,
	totalVotes,
} from "./-poll-editor-state";

const votesLabel = (count: number) => `${count} ${count === 1 ? "vote" : "votes"}`;

function RemoveOption({ row, onRemove }: { row: PollOptionRow; onRemove: () => void }) {
	if (row.votes > 0)
		return (
			<ConfirmDeleteButton
				label="Remove option"
				message={`Removing this option also deletes its ${votesLabel(row.votes)}.`}
				onConfirm={onRemove}
			/>
		);
	return (
		<Button onPress={onRemove}>
			<img src="/images/icons/cross.png" alt="Remove option" />
		</Button>
	);
}

// A poll the thread's first post carries. Controlled: `value` is the poll (null
// for none) and `onChange` gets the whole updated state. Errors stay hidden until
// a submit has been attempted.
export function PollEditor({
	value,
	onChange,
	showErrors,
}: {
	value: PollState | null;
	onChange: (value: PollState | null) => void;
	showErrors: boolean;
}) {
	const id = useId();
	const perUserLabelId = `${id}-per-user`;

	const { dragAndDropHooks } = useDragAndDrop({
		getItems: (keys) => [...keys].map((key) => ({ "text/plain": String(key) })),
		onReorder: (event) => {
			if (!value) return;
			onChange({
				...value,
				options: moveRows(
					value.options,
					event.keys,
					event.target.key,
					event.target.dropPosition === "before" ? "before" : "after",
				),
			});
		},
	});

	if (!value)
		return (
			<button type="button" onClick={() => onChange(newPollState())}>
				Add a poll
			</button>
		);

	const errors = showErrors ? pollErrors(value) : { rows: {} };
	const voteTotal = totalVotes(value.options);
	const update = (patch: Partial<PollState>) => onChange({ ...value, ...patch });
	const updateRow = (key: string, patch: Partial<PollOptionRow>) =>
		update({
			options: value.options.map((row) =>
				row.key === key ? { ...row, ...patch } : row,
			),
		});
	const perUserChoices = Array.from(
		{ length: Math.max(1, value.options.length) },
		(_, index) => String(index + 1),
	);

	return (
		<div className={styles["poll-editor"]}>
			<div className={styles["field"]}>
				<label htmlFor={`${id}-question`}>Question</label>
				<input
					type="text"
					id={`${id}-question`}
					maxLength={MAX_POLL_TEXT_LENGTH}
					className={clsx(errors.question && "field-invalid")}
					value={value.question}
					onChange={(e) => update({ question: e.target.value })}
				/>
				{errors.question && <div className="error">{errors.question}</div>}
			</div>

			<div className={styles["field"]}>
				<span id={`${id}-options`}>Options</span>
				{/* "tab" keeps keystrokes inside a row's text input from being taken for
				    list navigation (arrows, typeahead, space). The rows' handlers close
				    over the whole poll, so `dependencies` stops GridList reusing a cached
				    row (an unchanged option object) whose handlers hold a stale poll. */}
				<GridList
					aria-labelledby={`${id}-options`}
					className={styles["options"]}
					items={value.options}
					dependencies={[value, showErrors]}
					keyboardNavigationBehavior="tab"
					dragAndDropHooks={dragAndDropHooks}
				>
					{(row) => {
						const index = value.options.findIndex((other) => other.key === row.key);
						const error = errors.rows[row.key];
						return (
							<GridListItem
								id={row.key}
								textValue={row.text || `Option ${index + 1}`}
								className={styles["option"]}
							>
								<div className={styles["option-main"]}>
									<Button slot="drag" className={styles["drag-handle"]}>
										≡
									</Button>
									<input
										type="text"
										aria-label={`Option ${index + 1}`}
										maxLength={MAX_POLL_TEXT_LENGTH}
										className={clsx(styles["option-text"], error && "field-invalid")}
										value={row.text}
										onChange={(e) => updateRow(row.key, { text: e.target.value })}
										onPaste={(e) => {
											const rows = applyPaste(
												value.options,
												row.key,
												e.clipboardData.getData("text"),
												e.currentTarget.selectionStart ?? 0,
												e.currentTarget.selectionEnd ?? 0,
											);
											if (!rows) return;
											e.preventDefault();
											update({ options: rows });
										}}
									/>
									{row.id !== null && (
										<span className={styles["votes"]}>{votesLabel(row.votes)}</span>
									)}
									<RemoveOption
										row={row}
										onRemove={() => onChange(removeOption(value, row.key))}
									/>
								</div>
								{error && <div className="error">{error}</div>}
							</GridListItem>
						);
					}}
				</GridList>
				{errors.options && <div className="error">{errors.options}</div>}
				<div>
					<button
						type="button"
						disabled={value.options.length >= MAX_POLL_OPTIONS}
						onClick={() => update({ options: [...value.options, newOptionRow()] })}
					>
						Add option
					</button>
				</div>
			</div>

			<div className={styles["setting"]}>
				<span id={perUserLabelId}>Options per voter</span>
				<Select
					id={`${id}-per-user`}
					ariaLabelledBy={perUserLabelId}
					items={perUserChoices}
					getId={(choice) => choice}
					getLabel={(choice) => choice}
					selectedId={String(value.optionsPerUser)}
					onChange={(choice) => update({ optionsPerUser: Number(choice) })}
				/>
			</div>
			<div className={styles["setting"]}>
				<Checkbox
					id={`${id}-revoting`}
					checked={value.allowRevoting}
					onChange={(checked) => update({ allowRevoting: checked })}
				/>
				<label htmlFor={`${id}-revoting`}>Allow changing votes</label>
			</div>

			<div className={styles["setting"]}>
				{voteTotal > 0 ? (
					<>
						<span>Remove poll</span>
						<ConfirmDeleteButton
							label="Remove poll"
							message={`Removing the poll also deletes its ${votesLabel(voteTotal)}.`}
							onConfirm={() => onChange(null)}
						/>
					</>
				) : (
					<button type="button" onClick={() => onChange(null)}>
						Remove poll
					</button>
				)}
			</div>
		</div>
	);
}

// Whether the poll, if there is one, has problems to fix before posting.
export function pollHasErrors(value: PollState | null): boolean {
	return value !== null && hasPollErrors(pollErrors(value));
}
