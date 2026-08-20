import clsx from "clsx";
import type { ReactNode } from "react";
import FateDie from "#/components/dice/FateDie";
import StarWarsFFGDie from "#/components/dice/StarWarsFFGDie";
import type {
	BasicDiceTerm,
	BasicRollResult,
	DiceSystem,
	FateRollResult,
	FengShuiRollResult,
	RollDiceResult,
	StarWarsFFGRollResult,
} from "#/queries/dice";
import styles from "./RollResultDisplay.module.css";

function BasicTermValues({ term }: { term: BasicDiceTerm }) {
	const items = term.rolls.map((value, index) => {
		const dropped = term.dropped.includes(index);
		if (Array.isArray(value)) {
			return (
				// biome-ignore lint/suspicious/noArrayIndexKey: rolls are positional, not unique
				<span key={index} className={clsx(dropped && styles.dropped)}>
					{value.map((chainValue, chainIndex) => (
						<span
							// biome-ignore lint/suspicious/noArrayIndexKey: rolls are positional, not unique
							key={chainIndex}
							className={clsx(chainIndex < value.length - 1 && styles.rerolled)}
						>
							{chainValue}
						</span>
					))}
				</span>
			);
		}
		return (
			// biome-ignore lint/suspicious/noArrayIndexKey: rolls are positional, not unique
			<span key={index} className={clsx(dropped && styles.dropped)}>
				{value}
			</span>
		);
	});

	return items.reduce<ReactNode[]>((acc, item, index) => {
		if (index > 0) acc.push(", ");
		acc.push(item);
		return acc;
	}, []);
}

function BasicRollDisplay({ result }: { result: BasicRollResult }) {
	const multipleGroups = result.groups.length > 1;

	return (
		<div className={styles.roll}>
			<p className={styles["roll-string"]}>
				{result.groups.map((g) => g.expression).join(", ")}
			</p>
			{result.groups.map((group) => (
				<p key={group.expression}>
					{multipleGroups && `${group.expression}: `}
					{group.terms.map((term, termIndex) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: terms are positional, not unique
						<span key={`${term.sides}-${termIndex}`}>
							{(termIndex > 0 || term.sign < 0) && (term.sign < 0 ? "- " : "+ ")}(
							<BasicTermValues term={term} />)
							{termIndex < group.terms.length - 1 && " "}
						</span>
					))}
					{group.modifier !== 0 &&
						(group.modifier < 0
							? ` - ${Math.abs(group.modifier)}`
							: ` + ${group.modifier}`)}
					{" = "}
					<span className={styles["roll-total"]}>{group.total}</span>
				</p>
			))}
			{multipleGroups && (
				<p>
					Total: <span className={styles["roll-total"]}>{result.total}</span>
				</p>
			)}
		</div>
	);
}

function FateRollDisplay({ result }: { result: FateRollResult }) {
	const sum = result.total - result.modifier;

	return (
		<div className={styles.roll}>
			<div className={styles["dice-row"]}>
				{result.rolls.map((value, index) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: rolls are positional, not unique
					<FateDie key={index} value={value as -1 | 0 | 1} />
				))}
			</div>
			<p>
				{result.positive} Positive, {result.blank} Blank, {result.negative} Negative -
				Total:{" "}
				{result.modifier !== 0 ? (
					<>
						{sum} ({result.modifier > 0 ? "+" : ""}
						{result.modifier}){" = "}
						<span className={styles["roll-total"]}>{result.total}</span>
					</>
				) : (
					<span className={styles["roll-total"]}>{result.total}</span>
				)}
			</p>
		</div>
	);
}

function FengShuiRollDisplay({ result }: { result: FengShuiRollResult }) {
	return (
		<div className={styles.roll}>
			<div>
				{result.action_value}
				{result.type !== "closed" ? (
					<>
						{" "}
						+ [ {result.positive.join(", ")} ] - [ {result.negative.join(", ")} ]
					</>
				) : (
					<>
						{" "}
						+ {result.positive[0]} - {result.negative[0]}
					</>
				)}
				{result.extra != null && ` + ${result.extra}`}
				{" = "}
				<span className={styles["roll-total"]}>{result.total}</span>
			</div>
		</div>
	);
}

function StarWarsFFGRollDisplay({ result }: { result: StarWarsFFGRollResult }) {
	const { totals } = result;
	const successTotal = totals.success + totals.triumph;
	const failureTotal = totals.failure + totals.despair;

	const rawParts: string[] = [];
	if (successTotal) rawParts.push(`${successTotal} Success`);
	if (totals.advantage) rawParts.push(`${totals.advantage} Advantage`);
	if (totals.triumph) rawParts.push(`${totals.triumph} Triumph`);
	if (failureTotal) rawParts.push(`${failureTotal} Failure`);
	if (totals.threat) rawParts.push(`${totals.threat} Threat`);
	if (totals.despair) rawParts.push(`${totals.despair} Despair`);
	if (totals.whiteDot)
		rawParts.push(
			`${totals.whiteDot} White Force Point${totals.whiteDot > 1 ? "s" : ""}`,
		);
	if (totals.blackDot)
		rawParts.push(
			`${totals.blackDot} Black Force Point${totals.blackDot > 1 ? "s" : ""}`,
		);

	const netParts: string[] = [];
	if (result.net_success !== 0) {
		netParts.push(
			`${Math.abs(result.net_success)} ${result.net_success > 0 ? "Success" : "Failure"}`,
		);
	}
	if (result.net_advantage !== 0) {
		netParts.push(
			`${Math.abs(result.net_advantage)} ${result.net_advantage > 0 ? "Advantage" : "Threat"}`,
		);
	}
	if (totals.triumph) netParts.push(`${totals.triumph} Triumph`);
	if (totals.despair) netParts.push(`${totals.despair} Despair`);

	return (
		<div className={styles.roll}>
			<div className={styles["dice-row"]}>
				{result.rolls.map((roll, index) => (
					<StarWarsFFGDie
						// biome-ignore lint/suspicious/noArrayIndexKey: rolls are positional, not unique
						key={index}
						dieType={roll.die}
						result={roll.result}
					/>
				))}
			</div>
			{rawParts.length > 0 && <p>{rawParts.join(", ")}</p>}
			{netParts.length > 0 && (
				<p>
					<strong>Total:</strong> {netParts.join(", ")}
				</p>
			)}
		</div>
	);
}

function RollResultDisplay({
	system,
	result,
}: {
	system: DiceSystem;
	result: RollDiceResult;
}) {
	switch (system) {
		case "basic":
			return <BasicRollDisplay result={result as BasicRollResult} />;
		case "fate":
			return <FateRollDisplay result={result as FateRollResult} />;
		case "fengshui":
			return <FengShuiRollDisplay result={result as FengShuiRollResult} />;
		case "starwarsffg":
			return <StarWarsFFGRollDisplay result={result as StarWarsFFGRollResult} />;
	}
}

export default RollResultDisplay;
