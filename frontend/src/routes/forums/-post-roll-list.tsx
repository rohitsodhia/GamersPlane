import clsx from "clsx";
import RollResultDisplay from "#/components/dice/RollResultDisplay";
import type { PostRoll } from "#/queries/posts";
import styles from "./-post-roll-list.module.css";
import {
	hiddenTag,
	rollDisplay,
	rollParens,
	SYSTEM_LABELS,
	summaryText,
} from "./-post-rolls";

function RollItem({ roll }: { roll: PostRoll }) {
	const display = rollDisplay(roll);
	const { hiddenFromOthers } = display;
	const tag = hiddenTag(hiddenFromOthers);
	const parens = rollParens(roll);
	const reasonText = display.reasonWithheld ? "Secret roll" : roll.reason;

	return (
		<li className={clsx(styles["roll"], styles[`roll-${roll.type}`])}>
			<div>
				{tag && <span className={styles["hidden-tag"]}>[{tag}] </span>}
				{reasonText && (
					<span className={clsx(hiddenFromOthers.reason && styles["hidden-part"])}>
						{reasonText}
					</span>
				)}
				{reasonText && parens && " – "}
				{parens && (
					<span className={clsx(hiddenFromOthers.dice && styles["hidden-part"])}>
						({parens})
					</span>
				)}
				<span className={styles["system"]}>
					{(reasonText || parens) && " · "}
					{SYSTEM_LABELS[roll.type]}
				</span>
			</div>
			<div className={styles["result"]}>
				{roll.result && (
					// Hidden dice also hide the faces shown here; others only see the total.
					<div
						className={clsx(
							(hiddenFromOthers.result || hiddenFromOthers.dice) &&
								styles["hidden-part"],
						)}
					>
						<RollResultDisplay system={roll.type} result={roll.result} compact />
					</div>
				)}
				{display.summaryOnly && roll.summary && <p>{summaryText(roll.summary)}</p>}
				{display.resultWithheld && (
					<span className={styles["system"]}>Result hidden</span>
				)}
			</div>
		</li>
	);
}

export function PostRollList({ rolls }: { rolls: PostRoll[] }) {
	if (rolls.length === 0) return null;
	return (
		<div className={styles["rolls"]}>
			<h4>Rolls</h4>
			<ul>
				{rolls.map((roll) => (
					<RollItem key={roll.id} roll={roll} />
				))}
			</ul>
		</div>
	);
}
