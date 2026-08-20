import { useMutation } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import RollResultDisplay from "#/components/dice/RollResultDisplay";
import StarWarsFFGDie from "#/components/dice/StarWarsFFGDie";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type DiceSystem,
	type FengShuiRollType,
	type RollDiceParams,
	type RollDiceResult,
	rollDice,
	type StarWarsFFGDieType,
} from "#/queries/dice";
import styles from "./dice.module.css";

const SYSTEM_LABELS: Record<DiceSystem, string> = {
	basic: "Basic Dice",
	starwarsffg: "Star Wars FFG",
	fate: "Fate Dice",
	fengshui: "Feng Shui Dice",
};

const BASIC_QUICK_DICE = [
	["d4", "d6", "d8", "d10"],
	["d12", "d20", "d100"],
];

const STARWARS_DICE: { type: StarWarsFFGDieType; label: string }[] = [
	{ type: "ability", label: "Ability" },
	{ type: "difficulty", label: "Difficulty" },
	{ type: "proficiency", label: "Proficiency" },
	{ type: "challenge", label: "Challenge" },
	{ type: "boost", label: "Boost" },
	{ type: "setback", label: "Setback" },
];

type RollEntry = {
	id: string;
	system: DiceSystem;
	result: RollDiceResult;
};

type PoolDie = {
	id: string;
	type: StarWarsFFGDieType;
};

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}

export const Route = createFileRoute("/tools/dice")({
	component: RouteComponent,
});

function RouteComponent() {
	const [system, setSystem] = useState<DiceSystem>("basic");
	const [rolls, setRolls] = useState<RollEntry[]>([]);

	const [basicDice, setBasicDice] = useState("");
	const [rerollAces, setRerollAces] = useState(false);

	const [pool, setPool] = useState<PoolDie[]>([]);

	const [fateCount, setFateCount] = useState("4");

	const [fengshuiAV, setFengshuiAV] = useState("0");
	const [fengshuiType, setFengshuiType] = useState<FengShuiRollType>("standard");

	const rollMutation = useMutation({
		mutationFn: rollDice,
		onSuccess: (result, variables) => {
			setRolls((prev) => [
				{ id: crypto.randomUUID(), system: variables.system, result },
				...prev,
			]);
		},
	});

	const doRoll = (params: RollDiceParams) => rollMutation.mutate(params);

	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMarginedH1.ref}>
				Dice Roller
			</h1>

			<div
				className={styles["main-wrapper"]}
				style={{ marginInline: `${hbMarginedH1.margin}px` }}
			>
				<div className={styles.roller}>
					<div className="controls-container">
						<div className="trapezoid">
							<select
								className={styles["system-select"]}
								value={system}
								onChange={(e) => setSystem(e.target.value as DiceSystem)}
							>
								<option value="basic">Basic Dice</option>
								<option value="starwarsffg">Star Wars FFG</option>
								<option value="fate">Fate Dice</option>
								<option value="fengshui">Feng Shui</option>
							</select>
						</div>
					</div>
					<h2 className="headerbar hb-dark" ref={hbMarginedH2.ref}>
						{SYSTEM_LABELS[system]}
					</h2>

					<div style={{ marginInline: `${hbMarginedH2.margin}px` }}>
						{system === "basic" && (
							<div>
								<p>
									Dice should be in the format
									<br />
									(number of dice)d(die type)(modifier)
								</p>
								<p>Separate rolls should be separated by commas or on new lines.</p>
								<p>
									<i>Example: 2d4, 3d6+4</i>
								</p>
								<form
									className={styles["basic-form"]}
									onSubmit={(e) => {
										e.preventDefault();
										if (basicDice.trim().length === 0) return;
										doRoll({ system: "basic", roll: basicDice, rerollAces });
									}}
								>
									<div className={styles["basic-fields"]}>
										<textarea
											id="basic-dice"
											className={styles["basic-dice-input"]}
											value={basicDice}
											onChange={(e) => setBasicDice(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
													e.preventDefault();
													e.currentTarget.form?.requestSubmit();
												}
											}}
										/>
										<div className={styles["btn-wrapper"]}>
											<button type="submit" className="skew-btn">
												Roll
											</button>
											<div className={styles["cb-wrapper"]}>
												<input
													id="basic-reroll-aces"
													type="checkbox"
													checked={rerollAces}
													onChange={(e) => setRerollAces(e.target.checked)}
												/>
												<label htmlFor="basic-reroll-aces">Reroll Aces</label>
											</div>
										</div>
									</div>
									<div className={styles["indiv-dice"]}>
										{BASIC_QUICK_DICE.map((row) => (
											<div key={row.join()}>
												{row.map((die) => (
													<button
														key={die}
														type="button"
														className="skew-btn"
														onClick={() =>
															doRoll({ system: "basic", roll: die, rerollAces })
														}
													>
														{die}
													</button>
												))}
											</div>
										))}
									</div>
								</form>
							</div>
						)}

						{system === "starwarsffg" && (
							<div className={styles["starwars-panel"]}>
								<div>
									<div className={styles["dice-pool"]}>
										{pool.map((die) => (
											<button
												key={die.id}
												type="button"
												title="Remove die"
												onClick={() =>
													setPool((p) => p.filter((other) => other.id !== die.id))
												}
											>
												<StarWarsFFGDie dieType={die.type} />
											</button>
										))}
									</div>
									<div className={styles["starwars-roll-wrapper"]}>
										<button
											type="button"
											className="skew-btn"
											disabled={pool.length === 0}
											onClick={() =>
												doRoll({
													system: "starwarsffg",
													roll: pool.map((die) => die.type).join(","),
												})
											}
										>
											Roll
										</button>
										<button type="button" onClick={() => setPool([])}>
											Clear
										</button>
									</div>
									<p>
										Click on a die above to remove it from the dice pool.
										<br />
										Click on a die below to add it to the dice pool.
									</p>
									<div className={styles["starwars-grid"]}>
										{STARWARS_DICE.map(({ type, label }) => (
											<button
												key={type}
												type="button"
												className={clsx(styles["add-dice-link"], styles[`add-${type}`])}
												onClick={() =>
													setPool((p) => [...p, { id: crypto.randomUUID(), type }])
												}
											>
												<StarWarsFFGDie dieType={type} />
												<span>{label}</span>
											</button>
										))}
										<div className={styles["starwars-grid-full"]}>
											<button
												type="button"
												className={styles["add-dice-link"]}
												onClick={() =>
													setPool((p) => [
														...p,
														{ id: crypto.randomUUID(), type: "force" },
													])
												}
											>
												<StarWarsFFGDie dieType="force" />
												<span>Force</span>
											</button>
										</div>
									</div>
								</div>
							</div>
						)}

						{system === "fate" && (
							<div className={styles["simple-panel"]}>
								<label htmlFor="fate-count">Number of dice: </label>
								<input
									id="fate-count"
									type="text"
									value={fateCount}
									autoComplete="off"
									onChange={(e) => setFateCount(e.target.value.replace(/\D/g, ""))}
								/>
								<button
									type="button"
									className="skew-btn"
									onClick={() =>
										doRoll({
											system: "fate",
											roll: String(clamp(Number.parseInt(fateCount, 10) || 1, 1, 50)),
										})
									}
								>
									Roll
								</button>
							</div>
						)}

						{system === "fengshui" && (
							<div className={styles["simple-panel"]}>
								<label htmlFor="fengshui-av">Action Value: </label>
								<input
									id="fengshui-av"
									type="number"
									min={0}
									step={1}
									value={fengshuiAV}
									onChange={(e) => setFengshuiAV(e.target.value)}
								/>
								<select
									id="fengshui-type"
									value={fengshuiType}
									onChange={(e) => setFengshuiType(e.target.value as FengShuiRollType)}
								>
									<option value="standard">Standard</option>
									<option value="fortune">Fortune</option>
									<option value="closed">Closed</option>
								</select>
								<button
									type="button"
									className="skew-btn"
									onClick={() =>
										doRoll({
											system: "fengshui",
											roll: String(clamp(Number.parseInt(fengshuiAV, 10) || 0, 0, 50)),
											rollType: fengshuiType,
										})
									}
								>
									Roll
								</button>
							</div>
						)}
					</div>
				</div>

				<div className={styles["dice-space"]}>
					{rollMutation.isError && (
						<p className={styles.error}>
							{rollMutation.error instanceof ApiError
								? rollMutation.error.errors.map((e) => e.detail).join(", ")
								: "Something went wrong rolling those dice."}
						</p>
					)}
					{rolls.map((entry, index) => (
						<div key={entry.id} className={clsx(index === 0 && styles["newest-roll"])}>
							<div>
								<RollResultDisplay system={entry.system} result={entry.result} />
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
