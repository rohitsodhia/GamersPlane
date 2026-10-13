import { useMutation } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import { ApiError } from "#/lib/api";
import { type RollDiceResult, rollDice } from "#/queries/dice";
import BarPopover from "./BarPopover";
import RollResultDisplay from "./dice/RollResultDisplay";
import styles from "./GameBarTools.module.css";

const QUICK_DICE = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"];
const MAX_ROLLS = 10;

type RollEntry = { id: string; result: RollDiceResult };

// Basic dice only; the other systems live on the dice tool page. The history is
// this viewer's alone: it isn't posted anywhere or kept past the page.
export default function DiceMenu() {
	const [rolls, setRolls] = useState<RollEntry[]>([]);
	const [custom, setCustom] = useState("");

	const rollMutation = useMutation({
		mutationFn: rollDice,
		onSuccess: (result) => {
			setRolls((prev) =>
				[{ id: crypto.randomUUID(), result }, ...prev].slice(0, MAX_ROLLS),
			);
		},
	});

	const roll = (expression: string) =>
		rollMutation.mutate({ system: "basic", roll: expression });

	return (
		<BarPopover label="Dice" placement="top end" dialogClassName={styles["tool"]}>
			<div className={styles["quick-dice"]}>
				{QUICK_DICE.map((die) => (
					<Button
						key={die}
						className={styles["small-btn"]}
						onPress={() => roll(`1${die}`)}
					>
						{die}
					</Button>
				))}
			</div>
			<form
				className={styles["custom-roll"]}
				onSubmit={(e) => {
					e.preventDefault();
					if (custom.trim().length === 0) return;
					roll(custom);
				}}
			>
				<TextField
					aria-label="Custom roll"
					value={custom}
					onChange={setCustom}
					autoComplete="off"
				>
					<Input placeholder="2d6+3, 1d20" />
				</TextField>
				<Button type="submit" className={styles["small-btn"]}>
					Roll
				</Button>
			</form>
			{rollMutation.isError && (
				<p role="alert" className={styles["error"]}>
					{rollMutation.error instanceof ApiError
						? rollMutation.error.errors.map((e) => e.detail).join(", ")
						: "Something went wrong rolling those dice."}
				</p>
			)}
			{rolls.length > 0 && (
				<div className={styles["rolls-actions"]}>
					<Button className={styles["clear"]} onPress={() => setRolls([])}>
						[ Clear ]
					</Button>
				</div>
			)}
			<ul className={styles["rolls"]} aria-label="Recent rolls">
				{rolls.map((entry) => (
					<li key={entry.id} className={styles["roll"]}>
						<RollResultDisplay system="basic" result={entry.result} />
					</li>
				))}
			</ul>
			<Link to="/tools/dice" className={styles["more-dice"]}>
				Other dice systems
			</Link>
		</BarPopover>
	);
}
