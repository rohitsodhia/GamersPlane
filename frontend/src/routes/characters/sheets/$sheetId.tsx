import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { FadeOut } from "#/components/FadeOut";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useFlash } from "#/lib/use-flash";
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
			system={sheet.system.id}
			layout={sheet.layout}
		/>
	);
}

type SheetView = "visual" | "code";

function SheetEditor({
	sheetId,
	name,
	system,
	layout,
}: {
	sheetId: number;
	name: string;
	system: string;
	layout: SheetSchema | null | undefined;
}) {
	const queryClient = useQueryClient();
	const [view, setView] = useState<SheetView>("visual");
	const [draft, setDraft] = useState(() => JSON.stringify(layout ?? {}, null, 4));
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
		if (!schema || saving) return;
		setSaving(true);
		setSaveError(null);
		try {
			const updated = await updateCharacterSheet(sheetId, schema);
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

	// TODO: seed `initialValues` from the character's stored `values` once the
	// character fill route exists — this route currently just exercises the
	// renderer + value store against the sheet's own layout.
	return (
		<div className={styles["sheet-editor"]}>
			<h1 className="headerbar">{name}</h1>

			<div className={styles["sheet-logo"]}>
				<img src={`/images/logos/${system}.png`} alt={system} title={system} />
			</div>

			<div className="controls-container">
				<button
					type="button"
					className="skew-btn"
					onClick={handleSave}
					disabled={saving || !schema}
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
