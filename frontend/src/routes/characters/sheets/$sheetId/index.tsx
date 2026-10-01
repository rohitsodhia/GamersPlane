import { useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import { lazy, type ReactNode, Suspense, useState } from "react";
import { z } from "zod";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { FadeOut } from "#/components/FadeOut";
import LoadingSpinner from "#/components/LoadingSpinner";
import { TiptapContent } from "#/components/TiptapContent";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useFlash } from "#/lib/use-flash";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type CharacterSheet,
	characterSheetQueryOptions,
	characterSheetVersionsQueryOptions,
	discardCharacterSheetDraft,
	publishCharacterSheet,
	updateCharacterSheet,
} from "#/queries/characterSheet";
import { meQueryOptions } from "#/queries/me";
import { SheetRenderer } from "../-components/SheetRenderer";
import { SheetValuesProvider, useSheetStore } from "../-components/sheet-values";
import type { SheetSchema } from "../-components/types";
import styles from "./index.module.css";

// CodeMirror is heavy and only needed on the Code tab.
const JsonEditor = lazy(() => import("#/components/JsonEditor"));

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
			removedFields={sheet.removed_fields}
			isOwner={isOwner}
			from={from}
		/>
	);
}

type SheetView = "visual" | "code";

// JSON.parse only reports where it failed inside its message, in the engine's
// own format: V8 gives "at position N", Firefox "at line L column C", and
// Safari neither (null here).
function jsonErrorLocation(message: string, text: string) {
	const byPosition = message.match(/at position (\d+)/);
	if (byPosition) {
		const offset = Math.min(Number(byPosition[1]), text.length);
		const before = text.slice(0, offset);
		return {
			offset,
			line: before.split("\n").length,
			column: offset - before.lastIndexOf("\n"),
		};
	}
	const byLine = message.match(/at line (\d+) column (\d+)/);
	if (byLine) {
		const line = Number(byLine[1]);
		const column = Number(byLine[2]);
		const lineStart = text
			.split("\n")
			.slice(0, line - 1)
			.reduce((sum, l) => sum + l.length + 1, 0);
		return { offset: Math.min(lineStart + column - 1, text.length), line, column };
	}
	return null;
}

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
	removedFields,
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
	removedFields: CharacterSheet["removed_fields"];
	isOwner: boolean;
	from: "library" | undefined;
}) {
	const queryClient = useQueryClient();
	const [view, setView] = useState<SheetView>("visual");
	// Where to put the cursor when the Code tab opens from a JSON error link.
	const [codeCursor, setCodeCursor] = useState<number | undefined>(undefined);
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
	const [confirmingDiscard, setConfirmingDiscard] = useState(false);
	const [discardError, setDiscardError] = useState<string | null>(null);
	const [confirmingPublish, setConfirmingPublish] = useState(false);

	// The textarea is the source of truth in "code" mode — parse it on every
	// render so edits flow straight into the renderer.
	let schema: SheetSchema | null = null;
	let parseError: string | null = null;
	try {
		schema = JSON.parse(draft) as SheetSchema;
	} catch (err) {
		parseError = err instanceof Error ? err.message : String(err);
	}
	const errorLocation = parseError ? jsonErrorLocation(parseError, draft) : null;

	const hasLayout = Array.isArray(schema?.elements) && schema.elements.length > 0;

	// Only a draft has a changelog to edit, and v1 has nothing to log changes
	// against.
	const showChangelog = isDraft && latestVersionNumber !== null;
	// A never-published sheet's draft is its only version, so there's nothing
	// to fall back to.
	const canDiscard = isOwner && isDraft && latestVersionNumber !== null;

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

	const save = async (layout: SheetSchema): Promise<CharacterSheet> => {
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
		return updated;
	};

	const handleSave = () =>
		withSaving(async () => {
			await save(schema as SheetSchema);
			showFlash("Saved");
		});

	// Saves first, so what's published is what's on screen, not the last save.
	// A draft that drops fields stops to confirm; confirming saves again, and
	// only publishes if that save drops nothing beyond what was confirmed, so
	// edits made while the confirmation was open can't slip through unseen.
	const handlePublish = (confirmedIds?: Set<string>) =>
		withSaving(async () => {
			const saved = await save(schema as SheetSchema);
			const unconfirmed = saved.removed_fields.filter(
				(field) => !confirmedIds?.has(field.id),
			);
			if (unconfirmed.length > 0) {
				setConfirmingPublish(true);
				return;
			}
			setConfirmingPublish(false);
			const published = await publishCharacterSheet(sheetId);
			queryClient.setQueryData(characterSheetQueryOptions(sheetId).queryKey, published);
			queryClient.invalidateQueries({
				queryKey: characterSheetVersionsQueryOptions(sheetId).queryKey,
			});
			// The changelog is now frozen on the published version; the next
			// draft starts its own.
			setChangelogInput(emptyContent);
			showFlash("Published");
		});

	// Not through `withSaving`: discarding should work even when the code
	// doesn't parse, and its errors belong in the confirmation, not the save bar.
	const handleDiscard = async () => {
		if (saving) return;
		setSaving(true);
		setDiscardError(null);
		try {
			const published = await discardCharacterSheetDraft(sheetId);
			queryClient.setQueryData(characterSheetQueryOptions(sheetId).queryKey, published);
			setDraft(JSON.stringify(published.layout, null, 4));
			setChangelogInput(emptyContent);
			setConfirmingDiscard(false);
			setConfirmingPublish(false);
			showFlash("Draft discarded");
		} catch (err) {
			setDiscardError(
				err instanceof ApiError
					? err.errors.map((e) => e.detail).join(" ")
					: "Something went wrong.",
			);
		} finally {
			setSaving(false);
		}
	};

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

			{isDraft && removedFields.length > 0 ? (
				<p className={styles["removed-fields-notice"]}>
					This draft removes {removedFields.length === 1 ? "a field" : "fields"} from
					the published version: {removedFields.map((field) => field.label).join(", ")}
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
				{canDiscard ? (
					<>
						<div>
							<button
								type="button"
								className={styles["link-button"]}
								aria-expanded={confirmingDiscard}
								aria-controls="discard-draft-confirm"
								onClick={() => {
									setDiscardError(null);
									setConfirmingDiscard(true);
								}}
							>
								Discard Draft
							</button>
						</div>
						<SlideConfirm
							id="discard-draft-confirm"
							open={confirmingDiscard}
							disabled={saving}
							error={discardError}
							onConfirm={handleDiscard}
							onCancel={() => setConfirmingDiscard(false)}
						>
							<p>
								Discarding this draft will delete all changes and cannot be restored.
							</p>
						</SlideConfirm>
					</>
				) : null}
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
								onClick={() => handlePublish()}
								disabled={saving || !schema || !nameInput}
								aria-expanded={confirmingPublish}
								aria-controls="publish-confirm"
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
						onClick={() => {
							setCodeCursor(undefined);
							setView("code");
						}}
					>
						Code
					</button>
				</div>
			</div>

			{isOwner && isDraft ? (
				<SlideConfirm
					id="publish-confirm"
					open={confirmingPublish}
					className={styles["publish-confirm"]}
					disabled={saving}
					// Errors land in the save bar just above.
					error={null}
					onConfirm={() =>
						handlePublish(new Set(removedFields.map((field) => field.id)))
					}
					onCancel={() => setConfirmingPublish(false)}
				>
					<p>
						Publishing will remove{" "}
						{removedFields.length === 1 ? "this field" : "these fields"}:{" "}
						{removedFields.map((field) => field.label).join(", ")}. Characters moved to
						the new version will lose their values in{" "}
						{removedFields.length === 1 ? "it" : "them"}.
					</p>
				</SlideConfirm>
			) : null}

			{view === "visual" ? (
				<div className={styles["visual-display"]}>
					{parseError ? (
						<p className="error">
							JSON Error:{" "}
							{errorLocation ? (
								<button
									type="button"
									className={styles["error-link"]}
									onClick={() => {
										setCodeCursor(errorLocation.offset);
										setView("code");
									}}
								>
									Line {errorLocation.line}, Position {errorLocation.column}
								</button>
							) : (
								parseError
							)}
						</p>
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
					<Suspense fallback={<LoadingSpinner />}>
						<JsonEditor
							value={draft}
							onChange={setDraft}
							readOnly={!isOwner}
							initialCursor={codeCursor}
							className={styles["json-editor"]}
						/>
					</Suspense>
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

// A confirmation that slides open beneath whatever triggers it. Closed, it's
// `inert`, so its buttons drop out of the tab order while hidden.
function SlideConfirm({
	id,
	open,
	className,
	disabled,
	error,
	onConfirm,
	onCancel,
	children,
}: {
	id: string;
	open: boolean;
	className?: string;
	disabled: boolean;
	error: string | null;
	onConfirm: () => void;
	onCancel: () => void;
	children: ReactNode;
}) {
	return (
		<div
			id={id}
			className={`${styles["confirm"]}${className ? ` ${className}` : ""}`}
			data-open={open}
			inert={!open}
		>
			<div className={styles["confirm-inner"]}>
				<div className={styles["confirm-box"]}>
					{children}
					<div className={styles["confirm-actions"]}>
						<button
							type="button"
							className="skew-btn"
							onClick={onConfirm}
							disabled={disabled}
						>
							Confirm
						</button>
						<button
							type="button"
							className="skew-btn"
							onClick={onCancel}
							disabled={disabled}
						>
							Cancel
						</button>
						{error ? <span className="error">{error}</span> : null}
					</div>
				</div>
			</div>
		</div>
	);
}
