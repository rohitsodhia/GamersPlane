import { useState } from "react";
import styles from "./-advanced-options.module.css";

type AdvancedOptionsValue = Record<string, unknown>;

function getPath(obj: AdvancedOptionsValue, path: string[]): unknown {
	return path.reduce<unknown>((acc, key) => {
		if (acc && typeof acc === "object") return (acc as AdvancedOptionsValue)[key];
		return undefined;
	}, obj);
}

function setPath(
	obj: AdvancedOptionsValue,
	path: string[],
	value: unknown,
): AdvancedOptionsValue {
	const [key, ...rest] = path;
	if (rest.length === 0) return { ...obj, [key]: value };
	const existing = obj[key];
	const nested =
		existing && typeof existing === "object" ? (existing as AdvancedOptionsValue) : {};
	return { ...obj, [key]: setPath(nested, rest, value) };
}

// The old site scraped dice-rule and GM-sheet "shortcuts" live out of two
// hardcoded forum threads by regex-matching a spoiler-tag HTML structure
// that markItUp produced. Posts are now stored as tiptap JSON with no
// equivalent spoiler node, so that scraping has no data to read anymore.
// Shortcuts need a real backing source (a DB table, or a static JSON file
// shipped with the app) before this section can come back; until then the
// background image field, checkboxes, and raw JSON editor below still work
// and write into the same `advanced_options` blob the shortcuts used to.
export function AdvancedOptions({
	value,
	onChange,
}: {
	value: AdvancedOptionsValue;
	onChange: (value: AdvancedOptionsValue) => void;
}) {
	const [rawText, setRawText] = useState(() => JSON.stringify(value, null, 2));
	const [jsonError, setJsonError] = useState(false);

	function updateValue(path: string[], val: unknown) {
		const next = setPath(value, path, val);
		onChange(next);
		setRawText(JSON.stringify(next, null, 2));
		setJsonError(false);
	}

	function handleRawBlur() {
		const trimmed = rawText.trim();
		if (trimmed === "") {
			onChange({});
			setJsonError(false);
			return;
		}
		try {
			const parsed = JSON.parse(trimmed);
			if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
				onChange(parsed);
				setJsonError(false);
			} else {
				setJsonError(true);
			}
		} catch {
			setJsonError(true);
		}
	}

	return (
		<details className={styles["advanced-options"]}>
			<summary>Advanced rules definitions</summary>
			<div className={styles.content}>
				<p className="explanation">
					See the{" "}
					<a href="/forums/thread/22053/" target="guidesForum">
						guides forum
					</a>{" "}
					for help configuring these rules.
				</p>

				<div className={styles.field}>
					<label htmlFor="adr-background">Background image</label>
					<input
						id="adr-background"
						type="text"
						value={
							(getPath(value, ["background", "image"]) as string | undefined) ?? ""
						}
						onChange={(e) => updateValue(["background", "image"], e.target.value)}
					/>
				</div>

				<p className="explanation">
					Community dice-rule and GM-sheet shortcuts aren't available yet — the old
					version scraped them live from forum threads 22053 and 23143, which relied on
					a spoiler markup pattern the rebuilt forums no longer produce. These need a
					real data source before they can be listed here again.
				</p>

				<div className={styles["checked-row"]}>
					<label htmlFor="adr-gm-exclude-npcs">GM - exclude NPC sheets:</label>
					<input
						id="adr-gm-exclude-npcs"
						type="checkbox"
						checked={Boolean(
							getPath(value, ["characterSheetIntegration", "gmExcludeNpcs"]),
						)}
						onChange={(e) =>
							updateValue(
								["characterSheetIntegration", "gmExcludeNpcs"],
								e.target.checked,
							)
						}
					/>
				</div>
				<div className={styles["checked-row"]}>
					<label htmlFor="adr-gm-exclude-pcs">GM - exclude PC sheets:</label>
					<input
						id="adr-gm-exclude-pcs"
						type="checkbox"
						checked={Boolean(
							getPath(value, ["characterSheetIntegration", "gmExcludePcs"]),
						)}
						onChange={(e) =>
							updateValue(
								["characterSheetIntegration", "gmExcludePcs"],
								e.target.checked,
							)
						}
					/>
				</div>
				<div className={styles["checked-row"]}>
					<label htmlFor="adr-reroll-aces">Reroll aces by default:</label>
					<input
						id="adr-reroll-aces"
						type="checkbox"
						checked={Boolean(getPath(value, ["diceDefaults", "rerollAces"]))}
						onChange={(e) =>
							updateValue(["diceDefaults", "rerollAces"], e.target.checked)
						}
					/>
				</div>

				<div className={styles.field}>
					<label htmlFor="adr-json">Raw options (JSON)</label>
					<textarea
						id="adr-json"
						value={rawText}
						onChange={(e) => setRawText(e.target.value)}
						onBlur={handleRawBlur}
						className={jsonError ? "field-invalid" : ""}
					/>
					{jsonError && (
						<p className="error">This is not valid JSON and won't be saved.</p>
					)}
				</div>
			</div>
		</details>
	);
}
