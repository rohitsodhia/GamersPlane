import clsx from "clsx";
import { Checkbox } from "#/components/Checkbox";
import { Select } from "#/components/Select";
import type { DiceSystem, FengShuiRollType } from "#/queries/dice";
import type { DrawableDeck } from "#/queries/forums";
import { MAX_DRAWS_PER_POST, MAX_ROLLS_PER_POST } from "#/queries/posts";
import {
	type AttachmentAccess,
	type Attachments,
	attachmentErrors,
	availableDecks,
	type DrawRow,
	newDrawRow,
	newRollRow,
	type RollRow,
} from "./-attachment-rows";
import styles from "./-post-attachments.module.css";

const SYSTEMS: { value: DiceSystem; label: string; placeholder: string }[] = [
	{ value: "basic", label: "Basic Dice", placeholder: "2d6+1, 1d20" },
	{
		value: "starwarsffg",
		label: "Star Wars FFG",
		placeholder: "ability,proficiency,boost",
	},
	{ value: "fate", label: "Fate Dice", placeholder: "Number of dice, e.g. 4" },
	{ value: "fengshui", label: "Feng Shui Dice", placeholder: "Action value, e.g. 12" },
];

const FENGSHUI_ROLL_TYPES: { value: FengShuiRollType; label: string }[] = [
	{ value: "standard", label: "Standard" },
	{ value: "fortune", label: "Fortune" },
	{ value: "closed", label: "Closed" },
];

function LabelledCheckbox({
	id,
	label,
	checked,
	onChange,
}: {
	id: string;
	label: string;
	checked: boolean;
	onChange: (checked: boolean) => void;
}) {
	return (
		<span className={styles["labelled"]}>
			<Checkbox id={id} checked={checked} onChange={onChange} />
			<label htmlFor={id}>{label}</label>
		</span>
	);
}

function RollEditor({
	row,
	error,
	onChange,
	onRemove,
}: {
	row: RollRow;
	error: string | undefined;
	onChange: (patch: Partial<RollRow>) => void;
	onRemove: () => void;
}) {
	const system = SYSTEMS.find((candidate) => candidate.value === row.system);
	return (
		<li className={styles["row"]}>
			<div className={styles["row-main"]}>
				<Select
					id={`roll-system-${row.key}`}
					ariaLabel="Dice system"
					items={SYSTEMS}
					getId={(item) => item.value}
					getLabel={(item) => item.label}
					selectedId={row.system}
					onChange={(value) => onChange({ system: value as DiceSystem })}
				/>
				<input
					type="text"
					aria-label="Roll"
					className={clsx(styles["grow"], error && "field-invalid")}
					placeholder={system?.placeholder}
					value={row.roll}
					onChange={(e) => onChange({ roll: e.target.value })}
				/>
				<button type="button" onClick={onRemove}>
					Remove
				</button>
			</div>
			<input
				type="text"
				aria-label="Reason"
				placeholder="Reason (optional)"
				maxLength={100}
				value={row.reason}
				onChange={(e) => onChange({ reason: e.target.value })}
			/>
			<div className={styles["row-options"]}>
				{row.system === "basic" && (
					<LabelledCheckbox
						id={`roll-reroll-aces-${row.key}`}
						label="Reroll aces"
						checked={row.rerollAces}
						onChange={(checked) => onChange({ rerollAces: checked })}
					/>
				)}
				{row.system === "fate" && (
					<label>
						Modifier{" "}
						<input
							type="number"
							step={1}
							className={styles["number"]}
							value={row.modifier}
							onChange={(e) => onChange({ modifier: e.target.value })}
						/>
					</label>
				)}
				{row.system === "fengshui" && (
					<span className={styles["labelled"]}>
						<span id={`roll-type-label-${row.key}`}>Roll type</span>
						<Select
							id={`roll-type-${row.key}`}
							ariaLabelledBy={`roll-type-label-${row.key}`}
							items={FENGSHUI_ROLL_TYPES}
							getId={(item) => item.value}
							getLabel={(item) => item.label}
							selectedId={row.rollType}
							onChange={(value) => onChange({ rollType: value as FengShuiRollType })}
						/>
					</span>
				)}
				<LabelledCheckbox
					id={`roll-hide-reason-${row.key}`}
					label="Hide reason"
					checked={row.hideReason}
					onChange={(checked) => onChange({ hideReason: checked })}
				/>
				<LabelledCheckbox
					id={`roll-hide-dice-${row.key}`}
					label="Hide dice"
					checked={row.hideDice}
					onChange={(checked) => onChange({ hideDice: checked })}
				/>
				<LabelledCheckbox
					id={`roll-hide-result-${row.key}`}
					label="Hide result"
					checked={row.hideResult}
					onChange={(checked) => onChange({ hideResult: checked })}
				/>
			</div>
			{error && <div className="error">{error}</div>}
		</li>
	);
}

function DrawEditor({
	row,
	decks,
	choices,
	error,
	onChange,
	onRemove,
}: {
	row: DrawRow;
	decks: DrawableDeck[];
	choices: DrawableDeck[];
	error: string | undefined;
	onChange: (patch: Partial<DrawRow>) => void;
	onRemove: () => void;
}) {
	const deck = decks.find((candidate) => candidate.id === row.deckId);
	return (
		<li className={styles["row"]}>
			<div className={styles["row-main"]}>
				<Select
					id={`draw-deck-${row.key}`}
					ariaLabel="Deck"
					className={styles["grow"]}
					items={choices}
					getId={(choice) => String(choice.id)}
					getLabel={(choice) => `${choice.label} (${choice.remaining} left)`}
					selectedId={row.deckId === null ? "" : String(row.deckId)}
					onChange={(value) => onChange({ deckId: Number(value) })}
				/>
				<input
					type="number"
					aria-label="Cards to draw"
					className={styles["number"]}
					min={1}
					max={deck?.remaining}
					step={1}
					value={row.count}
					onChange={(e) => onChange({ count: e.target.value })}
				/>
				<button type="button" onClick={onRemove}>
					Remove
				</button>
			</div>
			<input
				type="text"
				aria-label="Reason"
				placeholder="Reason (required)"
				maxLength={100}
				className={clsx(error && !row.reason.trim() && "field-invalid")}
				value={row.reason}
				onChange={(e) => onChange({ reason: e.target.value })}
			/>
			{error && <div className="error">{error}</div>}
		</li>
	);
}

// Rolls and draws a post adds when it's saved. Controlled: `value` is the rows
// and `onChange` gets the whole updated set; the owner clears it after posting.
export function PostAttachmentsEditor({
	value,
	onChange,
	access,
	decks,
	showErrors,
}: {
	value: Attachments;
	onChange: (value: Attachments) => void;
	access: AttachmentAccess;
	decks: DrawableDeck[];
	// Row errors stay hidden until a submit has been attempted.
	showErrors: boolean;
}) {
	const errors = showErrors ? attachmentErrors(value, access, decks) : {};
	const showDraws = access.draws && decks.length > 0;

	const updateRoll = (key: string, patch: Partial<RollRow>) =>
		onChange({
			...value,
			rolls: value.rolls.map((row) => (row.key === key ? { ...row, ...patch } : row)),
		});
	const updateDraw = (key: string, patch: Partial<DrawRow>) =>
		onChange({
			...value,
			draws: value.draws.map((row) => (row.key === key ? { ...row, ...patch } : row)),
		});

	return (
		<div className={styles["attachments"]}>
			{access.rolls && (
				<section>
					<h3>Rolls</h3>
					{value.rolls.length > 0 && (
						<ul className={styles["rows"]}>
							{value.rolls.map((row) => (
								<RollEditor
									key={row.key}
									row={row}
									error={errors[row.key]}
									onChange={(patch) => updateRoll(row.key, patch)}
									onRemove={() =>
										onChange({
											...value,
											rolls: value.rolls.filter((other) => other.key !== row.key),
										})
									}
								/>
							))}
						</ul>
					)}
					<button
						type="button"
						disabled={value.rolls.length >= MAX_ROLLS_PER_POST}
						onClick={() =>
							onChange({ ...value, rolls: [...value.rolls, newRollRow()] })
						}
					>
						Add roll
					</button>
				</section>
			)}
			{showDraws && (
				<section>
					<h3>Draws</h3>
					{value.draws.length > 0 && (
						<ul className={styles["rows"]}>
							{value.draws.map((row) => (
								<DrawEditor
									key={row.key}
									row={row}
									decks={decks}
									choices={availableDecks(decks, value.draws, row.key)}
									error={errors[row.key]}
									onChange={(patch) => updateDraw(row.key, patch)}
									onRemove={() =>
										onChange({
											...value,
											draws: value.draws.filter((other) => other.key !== row.key),
										})
									}
								/>
							))}
						</ul>
					)}
					<button
						type="button"
						disabled={
							value.draws.length >= MAX_DRAWS_PER_POST ||
							availableDecks(decks, value.draws, null).length === 0
						}
						onClick={() =>
							onChange({
								...value,
								draws: [...value.draws, newDrawRow(decks, value.draws)],
							})
						}
					>
						Add draw
					</button>
				</section>
			)}
		</div>
	);
}
