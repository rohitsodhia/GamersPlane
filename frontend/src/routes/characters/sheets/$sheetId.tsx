import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { FadeOut } from "#/components/FadeOut";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useFlash } from "#/lib/use-flash";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	characterSheetQueryOptions,
	updateCharacterSheet,
} from "#/queries/characterSheet";
import { SheetRenderer } from "./-components/SheetRenderer";
import { SheetValuesProvider, useSheetStore } from "./-components/sheet-values";
import type { SheetSchema } from "./-components/types";
import styles from "./$sheetId.module.css";

export const Route = createFileRoute("/characters/sheets/$sheetId")({
	params: {
		parse: (params) => ({ sheetId: Number(params.sheetId) }),
	},
	loader: ({ context, params, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(characterSheetQueryOptions(params.sheetId)),
			location,
		),
	component: RouteComponent,
});

function RouteComponent() {
	const { sheetId } = Route.useParams();
	const { data: sheet } = useSuspenseQuery(characterSheetQueryOptions(sheetId));

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
}: {
	sheetId: number;
	name: string;
	description: string | null;
	system: string;
	layout: SheetSchema | null | undefined;
}) {
	const queryClient = useQueryClient();
	const [view, setView] = useState<SheetView>("visual");
	const [draft, setDraft] = useState(() => JSON.stringify(layout ?? {}, null, 4));
	const [nameInput, setNameInput] = useState(name);
	const [descriptionInput, setDescriptionInput] = useState(description ?? "");
	const [saved, flashSaved] = useFlash();
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

	const handleSave = async () => {
		if (!schema || !nameInput || saving) return;
		setSaving(true);
		setSaveError(null);
		try {
			const updated = await updateCharacterSheet(sheetId, {
				name: nameInput,
				description: descriptionInput ? descriptionInput : null,
				layout: schema,
			});
			queryClient.setQueryData(characterSheetQueryOptions(sheetId).queryKey, updated);
			flashSaved();
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

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	// TODO: seed `initialValues` from the character's stored `values` once the
	// character fill route exists — this route currently just exercises the
	// renderer + value store against the sheet's own layout.
	return (
		<div className={styles["sheet-editor"]}>
			<div style={{ marginLeft: hbMargined.margin }}>
				<Link to="/characters/sheets">Back to character sheets</Link>
			</div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{name}
			</h1>

			<div className={styles["sheet-logo"]}>
				<img src={`/images/logos/${system}.png`} alt={system} title={system} />
			</div>

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
					<textarea
						id="sheet-description"
						value={descriptionInput}
						onChange={(e) => setDescriptionInput(e.target.value)}
					/>
				</div>
			</div>

			<div className="controls-container">
				<button
					type="button"
					className="skew-btn"
					onClick={handleSave}
					disabled={saving || !schema || !nameInput}
				>
					Save
				</button>
				<FadeOut active={saved} className={styles["save-indicator"]}>
					Saved
				</FadeOut>
				{saveError ? <span className="error">{saveError}</span> : null}
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
