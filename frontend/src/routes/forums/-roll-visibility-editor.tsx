import type { PostRoll } from "#/queries/posts";
import { LabelledCheckbox } from "./-post-attachments";
import { SYSTEM_LABELS, type VisibilityFlags } from "./-post-rolls";
import styles from "./-roll-visibility-editor.module.css";

// Who may see which part of the post's existing rolls. Controlled: `value` is the
// flags by roll id and `onChange` gets the whole updated set.
export function RollVisibilityEditor({
	rolls,
	value,
	onChange,
}: {
	rolls: PostRoll[];
	value: Record<number, VisibilityFlags>;
	onChange: (value: Record<number, VisibilityFlags>) => void;
}) {
	const update = (id: number, patch: Partial<VisibilityFlags>) =>
		onChange({ ...value, [id]: { ...value[id], ...patch } });

	return (
		<ul className={styles["rolls"]}>
			{rolls.map((roll) => {
				const flags = value[roll.id];
				if (!flags) return null;
				return (
					<li key={roll.id} className={styles["roll"]}>
						<div className={styles["summary"]}>
							<strong>{SYSTEM_LABELS[roll.type]}</strong>: {roll.input}
							{roll.reason && (
								<span className={styles["reason"]}> ({roll.reason})</span>
							)}
						</div>
						<div className={styles["options"]}>
							<LabelledCheckbox
								id={`roll-visibility-reason-${roll.id}`}
								label="Hide reason"
								checked={flags.hideReason}
								onChange={(checked) => update(roll.id, { hideReason: checked })}
							/>
							<LabelledCheckbox
								id={`roll-visibility-dice-${roll.id}`}
								label="Hide dice"
								checked={flags.hideDice}
								onChange={(checked) => update(roll.id, { hideDice: checked })}
							/>
							<LabelledCheckbox
								id={`roll-visibility-result-${roll.id}`}
								label="Hide result"
								checked={flags.hideResult}
								onChange={(checked) => update(roll.id, { hideResult: checked })}
							/>
						</div>
					</li>
				);
			})}
		</ul>
	);
}
