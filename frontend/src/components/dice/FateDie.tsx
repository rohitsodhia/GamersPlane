import styles from "./FateDie.module.css";

function FateDie({ value }: { value: -1 | 0 | 1 }) {
	const label = value === 1 ? "Positive" : value === -1 ? "Negative" : "Blank";

	return (
		<div className={styles.die} title={label}>
			{value !== 0 && (
				<div className={styles.window}>
					<img
						src="/images/dice/fate/fate.png"
						alt={label}
						className={styles.sprite}
						style={{ top: value === 1 ? 0 : -30 }}
					/>
				</div>
			)}
			{value === 0 && <div className={styles.window} />}
		</div>
	);
}

export default FateDie;
