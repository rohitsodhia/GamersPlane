import { useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import { useState } from "react";
import { z } from "zod";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { FadeOut } from "#/components/FadeOut";
import { TiptapContent } from "#/components/TiptapContent";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useFlash } from "#/lib/use-flash";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	characterSheetQueryOptions,
	publishCharacterSheet,
	updateCharacterSheet,
} from "#/queries/characterSheet";
import { meQueryOptions } from "#/queries/me";
import { SheetRenderer } from "../-components/SheetRenderer";
import { SheetValuesProvider, useSheetStore } from "../-components/sheet-values";
import type { SheetSchema } from "../-components/types";
import styles from "./index.module.css";

export const Route = createFileRoute("/characters/sheets/$sheetId/")({
	params: {
		parse: (params) => ({ sheetId: Number(params.sheetId) }),
	},
	// `from` records which list this sheet was opened from, so the "Back to
	// ..." link above the sheet can return there — the router itself has no
	// reliable notion of "the previous page" (deep links, refreshes, and
	// browser back/forward all bypass it), so callers thread it through
	// explicitly on the Link that got us here.
	validateSearch: z.object({
		from: z.enum(["library"]).optional(),
	}),
	loader: ({ context, params, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(characterSheetQueryOptions(params.sheetId)),
			location,
		),
	component: RouteComponent,
});

function RouteComponent() {
	const { sheetId } = Route.useParams();
	const { from } = Route.useSearch();
	const { data: sheet } = useSuspenseQuery(characterSheetQueryOptions(sheetId));
	const { data: me } = useQuery(meQueryOptions);
	const isOwner = me !== undefined && me.id === sheet.creator.id;

	// Remount the editor when switching sheets so the code draft re-seeds from
	// the newly loaded layout.
	return (
		<SheetEditor
			key={sheetId}
			sheetId={sheetId}
			name={sheet.name}
			description={sheet.description}
			system={sheet.system.id}
			layout={sheet.layout}
			versionNumber={sheet.version_number}
			latestVersionNumber={sheet.latest_version_number}
			changelog={sheet.changelog}
			isDraft={sheet.is_draft}
			isOwner={isOwner}
			from={from}
		/>
	);
}

type SheetView = "visual" | "code";

function SheetEditor({
	sheetId,
	name,
	description,
	system,
	layout,
	versionNumber,
	latestVersionNumber,
	changelog,
	isDraft,
	isOwner,
	from,
}: {
	sheetId: number;
	name: string;
	description: JSONContent | null;
	system: string;
	layout: SheetSchema | null | undefined;
	versionNumber: number | null;
	latestVersionNumber: number | null;
	changelog: JSONContent | null;
	isDraft: boolean;
	isOwner: boolean;
	from: "library" | undefined;
}) {
	const queryClient = useQueryClient();
	const [view, setView] = useState<SheetView>("visual");
	const [draft, setDraft] = useState(() => JSON.stringify(layout ?? {}, null, 4));
	const [nameInput, setNameInput] = useState(name);
	const [descriptionInput, setDescriptionInput] = useState(description ?? emptyContent);
	// A changelog belongs to the draft. Viewing a published version, it's that
	// version's frozen entry, so start the next draft's changelog empty.
	const [changelogInput, setChangelogInput] = useState(
		(isDraft ? changelog : null) ?? emptyContent,
	);
	// One indicator for both actions, so an idle one doesn't hold open a gap
	// beside the other. The text outlives `flashing` so it can fade out.
	const [flashing, flash] = useFlash();
	const [flashMessage, setFlashMessage] = useState("");
	const showFlash = (message: string) => {
		setFlashMessage(message);
		flash();
	};
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState<string | null>(null);

	// The textarea is the source of truth in "code" mode — parse it on every
	// render so edits flow straight into the renderer.
	let schema: SheetSchema | null = null;
	let parseError: string | null = null;
	try {
		schema = JSON.parse(draft) as SheetSchema;
	} catch (err) {
		parseError = err instanceof Error ? err.message : String(err);
	}

	const hasLayout = Array.isArray(schema?.elements) && schema.elements.length > 0;

	// Only a draft has a changelog to edit, and v1 has nothing to log changes
	// against.
	const showChangelog = isDraft && latestVersionNumber !== null;

	// Runs `action` with the save controls locked, surfacing any API error.
	const withSaving = async (action: () => Promise<void>) => {
		if (!isOwner || !schema || !nameInput || saving) return;
		setSaving(true);
		setSaveError(null);
		try {
			await action();
		} catch (err) {
			setSaveError(
				err instanceof ApiError
					? err.errors.map((e) => e.detail).join(" ")
					: "Something went wrong.",
			);
		} finally {
			setSaving(false);
		}
	};

	const save = async (layout: SheetSchema) => {
		const updated = await updateCharacterSheet(sheetId, {
			name: nameInput,
			description: isContentEmpty(descriptionInput) ? null : descriptionInput,
			layout,
			changelog:
				!showChangelog || isContentEmpty(changelogInput) ? null : changelogInput,
		});
		queryClient.setQueryData(characterSheetQueryOptions(sheetId).queryKey, updated);
		// Pick up the ids the server minted (new fields, duplicates), so the
		// next save sends them back instead of minting fresh ones each time.
		setDraft(JSON.stringify(updated.layout, null, 4));
	};

	const handleSave = () =>
		withSaving(async () => {
			await save(schema as SheetSchema);
			showFlash("Saved");
		});

	// Saves first, so what's published is what's on screen, not the last save.
	const handlePublish = () =>
		withSaving(async () => {
			await save(schema as SheetSchema);
			const published = await publishCharacterSheet(sheetId);
			queryClient.setQueryData(characterSheetQueryOptions(sheetId).queryKey, published);
			// The changelog is now frozen on the published version; the next
			// draft starts its own.
			setChangelogInput(emptyContent);
			showFlash("Published");
		});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	const draftLabel = `Draft of v${(latestVersionNumber ?? 0) + 1}`;
	const versionLabel = isDraft ? draftLabel : `v${versionNumber}`;

	// TODO: seed `initialValues` from the character's stored `values` once the
	// character fill route exists — this route currently just exercises the
	// renderer + value store against the sheet's own layout.
	return (
		<div className={styles["sheet-editor"]}>
			<div style={{ marginLeft: hbMargined.margin }}>
				{from === "library" ? (
					<Link to="/characters/sheets/library">Back to character sheet library</Link>
				) : (
					<Link to="/characters/sheets">Back to character sheets</Link>
				)}
			</div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{name}
			</h1>

			{isDraft ? (
				<p className={styles["draft-notice"]}>
					You're viewing an unpublished draft. Other users see the latest published
					version.
				</p>
			) : null}

			<div className={styles["sheet-logo"]}>
				<img src={`/images/logos/${system}.png`} alt={system} title={system} />
			</div>

			{isOwner ? (
				<div className={`grid-layout ${styles["sheet-details"]}`}>
					<div>
						<label htmlFor="sheet-name" className="center-vertically">
							Name
						</label>
						<input
							id="sheet-name"
							type="text"
							value={nameInput}
							onChange={(e) => setNameInput(e.target.value)}
						/>
					</div>
					<div>
						<label htmlFor="sheet-description" className="push-down">
							Description
						</label>
						<Editor
							id="sheet-description"
							value={descriptionInput}
							onChange={setDescriptionInput}
						/>
					</div>
					{showChangelog ? (
						<div>
							<label htmlFor="sheet-changelog" className="push-down">
								Change Log
							</label>
							<Editor
								id="sheet-changelog"
								value={changelogInput}
								onChange={setChangelogInput}
							/>
						</div>
					) : null}
				</div>
			) : description && !isContentEmpty(description) ? (
				<TiptapContent content={description} className={styles["sheet-description"]} />
			) : null}

			<div className={styles["sheet-version"]}>
				Current Version: {versionLabel} (
				<Link to="/characters/sheets/$sheetId/changelog" params={{ sheetId }}>
					Change log
				</Link>
				)
			</div>

			<div className="controls-container">
				{isOwner && (
					<>
						<button
							type="button"
							className="skew-btn"
							onClick={handleSave}
							disabled={saving || !schema || !nameInput}
						>
							Save
						</button>
						{isDraft ? (
							<button
								type="button"
								className="skew-btn"
								onClick={handlePublish}
								disabled={saving || !schema || !nameInput}
							>
								Publish
							</button>
						) : (
							// Saving never edits a published version: layout
							// changes start a new draft on top of it.
							<span className={styles["save-hint"]}>
								Layout changes save as a {draftLabel}.
							</span>
						)}
						<FadeOut active={flashing} className={styles["save-indicator"]}>
							{flashMessage}
						</FadeOut>
						{saveError ? <span className="error">{saveError}</span> : null}
					</>
				)}
				<div className="trapezoid">
					<button
						type="button"
						className={view === "visual" ? "current" : undefined}
						onClick={() => setView("visual")}
					>
						Visual
					</button>
					<button
						type="button"
						className={view === "code" ? "current" : undefined}
						onClick={() => setView("code")}
					>
						Code
					</button>
				</div>
			</div>

			{view === "visual" ? (
				<div className={styles["visual-display"]}>
					{parseError ? (
						<p className="error">Invalid JSON: {parseError}</p>
					) : hasLayout ? (
						<SheetValuesProvider mode="edit">
							<SheetFillForm schema={schema as SheetSchema} />
						</SheetValuesProvider>
					) : (
						<p>This sheet doesn't have a layout yet.</p>
					)}
				</div>
			) : (
				<div className={styles["code-display"]}>
					<textarea
						value={draft}
						spellCheck={false}
						onChange={(e) => setDraft(e.target.value)}
						readOnly={!isOwner}
					/>
				</div>
			)}
		</div>
	);
}

function SheetFillForm({ schema }: { schema: SheetSchema }) {
	const store = useSheetStore();

	return (
		<form
			onSubmit={(e) => {
				e.preventDefault();
				// TODO: POST the snapshot to the character save endpoint once it exists.
				console.log("sheet values", store.snapshot());
			}}
		>
			<SheetRenderer schema={schema} />
		</form>
	);
}
