import clsx from "clsx";
import type { StarWarsFFGDieType } from "#/queries/dice";
import styles from "./StarWarsFFGDie.module.css";

const BACKGROUND_POSITIONS: Record<StarWarsFFGDieType, [number, number]> = {
	ability: [0, 0],
	proficiency: [-25, 0],
	difficulty: [-50, 0],
	challenge: [-75, 0],
	boost: [-100, 0],
	setback: [-125, 0],
	force: [-150, 0],
};

const FACE_POSITIONS: Record<string, [number, number]> = {
	success: [0, 0],
	advantage: [-25, 0],
	triumph: [-50, 0],
	success_success: [-75, 0],
	success_advantage: [-100, 0],
	advantage_advantage: [-125, 0],
	failure: [0, -50],
	threat: [-25, -50],
	despair: [-50, -50],
	failure_failure: [-75, -50],
	failure_threat: [-100, -50],
	threat_threat: [-125, -50],
	whiteDot: [0, -100],
	blackDot: [-25, -100],
	whiteDot_whiteDot: [-50, -100],
	blackDot_blackDot: [-75, -100],
};

function StarWarsFFGDie({
	dieType,
	result,
	className,
}: {
	dieType: StarWarsFFGDieType;
	result?: string;
	className?: string;
}) {
	const [bgX, bgY] = BACKGROUND_POSITIONS[dieType];
	const facePosition = result ? FACE_POSITIONS[result] : undefined;

	return (
		<div className={clsx(styles.window, className)}>
			<img
				src="/images/dice/starwarsffg/backgrounds.png"
				alt={dieType}
				className={styles.background}
				style={{ left: bgX, top: bgY }}
			/>
			{facePosition && (
				<img
					src="/images/dice/starwarsffg/faces.png"
					alt={result?.replace("_", " ")}
					title={result?.replace("_", " ")}
					className={styles.face}
					style={{ left: facePosition[0], top: facePosition[1] }}
				/>
			)}
		</div>
	);
}

export default StarWarsFFGDie;
