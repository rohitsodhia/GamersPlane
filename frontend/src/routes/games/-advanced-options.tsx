import clsx from "clsx";
import { useEffect, useState } from "react";
import { Checkbox } from "#/components/Checkbox";
import { Select } from "#/components/Select";
import {
	BACKGROUND_TYPES,
	backgroundFileError,
	backgroundStyle,
} from "#/lib/game-background";
import type { BackgroundPosition, BackgroundSize } from "#/queries/game";
import styles from "./-advanced-options.module.css";
import { type BackgroundDraft, imageWillExist } from "./-game-save";

type Option<T extends string> = { id: T; label: string };

const POSITIONS: Option<BackgroundPosition>[] = [
	{ id: "center", label: "Center" },
	{ id: "top", label: "Top" },
	{ id: "bottom", label: "Bottom" },
	{ id: "left", label: "Left" },
	{ id: "right", label: "Right" },
	{ id: "top left", label: "Top left" },
	{ id: "top right", label: "Top right" },
	{ id: "bottom left", label: "Bottom left" },
	{ id: "bottom right", label: "Bottom right" },
];

const SIZES: Option<BackgroundSize>[] = [
	{ id: "width", label: "Fit width" },
	{ id: "cover", label: "Fill the page" },
	{ id: "contain", label: "Show the whole image" },
];

const SIZE_DESCRIPTIONS: Record<BackgroundSize, string> = {
	width:
		"Stretches the image across the page's full width without distorting it. Extra height is cut off at the bottom, or left empty if the image is shorter than the page.",
	cover:
		"Fills the whole page, cropping the edges of the image if its shape doesn't match. Can look zoomed in on tall or narrow pages.",
	contain:
		"Shows the entire image without cropping, which can leave empty space at the sides or bottom.",
};

// Hidden for now: nobody in the old data used repeat, and the API no longer
// takes it. To bring it back, restore `repeat` on the API's BackgroundSettings
// and the frontend types, then un-comment this and the Repeat select below.
// const REPEATS: Option<BackgroundRepeat>[] = [
// 	{ id: "no-repeat", label: "Don't repeat" },
// 	{ id: "repeat", label: "Repeat" },
// 	{ id: "repeat-x", label: "Repeat horizontally" },
// 	{ id: "repeat-y", label: "Repeat vertically" },
// ];

// The old site scraped dice-rule and GM-sheet "shortcuts" live out of two
// hardcoded forum threads by regex-matching a spoiler-tag HTML structure
// that markItUp produced. Posts are now stored as tiptap JSON with no
// equivalent spoiler node, so that scraping has no data to read anymore.
// Shortcuts need a real backing source (a DB table, or a static JSON file
// shipped with the app) before this section can come back.
//
// The three checkboxes are placeholders: the API no longer accepts those
// options, so their state stays local to the form and is never sent.
export function AdvancedOptions({
	background,
	onBackgroundChange,
	existingUrl,
}: {
	background: BackgroundDraft;
	onBackgroundChange: (background: BackgroundDraft) => void;
	/** The uploaded image's URL, when the game already has one. */
	existingUrl: string | null;
}) {
	const [gmExcludeNpcs, setGmExcludeNpcs] = useState(false);
	const [gmExcludePcs, setGmExcludePcs] = useState(false);
	const [rerollAces, setRerollAces] = useState(false);
	const [fileError, setFileError] = useState<string | null>(null);
	const [stagedUrl, setStagedUrl] = useState<string | null>(null);

	useEffect(() => {
		if (!background.file) {
			setStagedUrl(null);
			return;
		}
		const url = URL.createObjectURL(background.file);
		setStagedUrl(url);
		return () => URL.revokeObjectURL(url);
	}, [background.file]);

	// Opens on load when the game already has options set. Read once, so it
	// doesn't fight the user toggling it or the staged edits below.
	const [startsOpen] = useState(existingUrl !== null);

	const hasImage = imageWillExist(existingUrl !== null, background);
	const previewUrl = background.file ? stagedUrl : existingUrl;

	function setSettings(changes: Partial<BackgroundDraft["settings"]>) {
		onBackgroundChange({
			...background,
			settings: { ...background.settings, ...changes },
		});
	}

	function pickFile(file: File | undefined) {
		if (!file) return;
		const error = backgroundFileError(file);
		setFileError(error);
		if (error) return;
		onBackgroundChange({ ...background, file, removed: false });
	}

	function removeImage() {
		setFileError(null);
		onBackgroundChange({ ...background, file: null, removed: true });
	}

	return (
		<details className={styles["advanced-options"]} open={startsOpen}>
			<summary>Advanced rules definitions</summary>
			<div className={clsx("grid-layout", styles["content"])}>
				<p className="explanation full-width">
					See the{" "}
					<a href="/forums/thread/22053/" target="guidesForum">
						guides forum
					</a>{" "}
					for help configuring these rules.
				</p>

				<p className="explanation full-width">
					Community dice-rule and GM-sheet shortcuts aren't available yet — the old
					version scraped them live from forum threads 22053 and 23143, which relied on
					a spoiler markup pattern the rebuilt forums no longer produce. These need a
					real data source before they can be listed here again.
				</p>

				<div className={styles["checked-row"]}>
					<label htmlFor="adr-gm-exclude-npcs">GM - exclude NPC sheets:</label>
					<Checkbox
						id="adr-gm-exclude-npcs"
						checked={gmExcludeNpcs}
						onChange={setGmExcludeNpcs}
					/>
				</div>
				<div className={styles["checked-row"]}>
					<label htmlFor="adr-gm-exclude-pcs">GM - exclude PC sheets:</label>
					<Checkbox
						id="adr-gm-exclude-pcs"
						checked={gmExcludePcs}
						onChange={setGmExcludePcs}
					/>
				</div>
				<div className={styles["checked-row"]}>
					<label htmlFor="adr-reroll-aces">Reroll aces by default:</label>
					<Checkbox
						id="adr-reroll-aces"
						checked={rerollAces}
						onChange={setRerollAces}
					/>
				</div>

				<div className={styles["background"]}>
					<h3 className="full-width">Background</h3>
					<p className="explanation full-width">
						The background shows behind the page content.
					</p>

					<div className={styles["field-with-hint"]}>
						<label htmlFor="adr-background-file">
							{hasImage ? "Replace image" : "Image"}
						</label>
						<div>
							<input
								id="adr-background-file"
								type="file"
								accept={BACKGROUND_TYPES.join(",")}
								onChange={(e) => {
									pickFile(e.target.files?.[0]);
									e.target.value = "";
								}}
							/>
						</div>
						<p className={clsx("explanation", styles["hint"])}>
							JPEG, PNG or WEBP, up to 10MB.
						</p>
						{fileError && <p className={clsx("error", styles["hint"])}>{fileError}</p>}
					</div>

					{background.removed && existingUrl !== null && !background.file && (
						<p className="explanation full-width">
							The background will be removed when you save.{" "}
							<button
								type="button"
								onClick={() => onBackgroundChange({ ...background, removed: false })}
							>
								Undo
							</button>
						</p>
					)}

					{hasImage && previewUrl && (
						<>
							<div
								className={styles["preview"]}
								style={{
									...backgroundStyle(background.settings, previewUrl),
									backgroundAttachment: "scroll",
								}}
								role="img"
								aria-label="Background preview"
							/>
							<div className={styles["settings"]}>
								<div className={styles["field"]}>
									<label htmlFor="adr-background-color">Color</label>
									<div>
										<input
											id="adr-background-color"
											type="color"
											value={background.settings.color ?? "#ffffff"}
											onChange={(e) => setSettings({ color: e.target.value })}
										/>{" "}
										{background.settings.color ? (
											<button
												type="button"
												onClick={() => setSettings({ color: null })}
											>
												Clear
											</button>
										) : (
											<span className="explanation">None</span>
										)}
									</div>
								</div>
								<div className={styles["field"]}>
									<label htmlFor="adr-background-position">Position</label>
									<Select
										id="adr-background-position"
										items={POSITIONS}
										getId={(option) => option.id}
										getLabel={(option) => option.label}
										selectedId={background.settings.position}
										onChange={(id) =>
											setSettings({ position: id as BackgroundPosition })
										}
									/>
								</div>
								<div className={styles["field-with-hint"]}>
									<label htmlFor="adr-background-size">Size</label>
									<Select
										id="adr-background-size"
										items={SIZES}
										getId={(option) => option.id}
										getLabel={(option) => option.label}
										selectedId={background.settings.size}
										onChange={(id) => setSettings({ size: id as BackgroundSize })}
									/>
									<p className={clsx("explanation", styles["hint"])}>
										{SIZE_DESCRIPTIONS[background.settings.size]}
									</p>
								</div>
								{/* Hidden, see REPEATS above.
								<div className={styles["field"]}>
									<label htmlFor="adr-background-repeat">Repeat</label>
									<Select
										id="adr-background-repeat"
										items={REPEATS}
										getId={(option) => option.id}
										getLabel={(option) => option.label}
										selectedId={background.settings.repeat}
										onChange={(id) => setSettings({ repeat: id as BackgroundRepeat })}
									/>
								</div>
								*/}
								<div className={styles["checked-row"]}>
									<label htmlFor="adr-background-fixed">
										Keep fixed while scrolling:
									</label>
									<Checkbox
										id="adr-background-fixed"
										checked={background.settings.fixed}
										onChange={(fixed) => setSettings({ fixed })}
									/>
								</div>
							</div>
							<div className={styles["actions"]}>
								<button type="button" onClick={removeImage}>
									Remove background
								</button>
							</div>
						</>
					)}
				</div>
			</div>
		</details>
	);
}
