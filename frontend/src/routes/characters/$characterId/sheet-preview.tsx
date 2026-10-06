import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import { isContentEmpty } from "#/components/Editor";
import { TiptapContent } from "#/components/TiptapContent";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { formatDate } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	characterQueryOptions,
	characterSheetMovePreviewQueryOptions,
	characterSheetMovesQueryOptions,
	moveCharacterSheet,
} from "#/queries/character";
import { characterSheetVersionsQueryOptions } from "#/queries/characterSheet";
import { meQueryOptions } from "#/queries/me";
import { SheetRenderer } from "../sheets/-components/SheetRenderer";
import { SheetValuesProvider } from "../sheets/-components/sheet-values";
import styles from "./character.module.css";
import previewStyles from "./sheet-preview.module.css";

// Shows a character on another sheet version before it moves there: a newer
// version of its sheet (an upgrade) or a version of a copy (a change).
export const Route = createFileRoute("/characters/$characterId/sheet-preview")({
	params: {
		parse: (params) => ({ characterId: Number(params.characterId) }),
	},
	validateSearch: z.object({
		sheet: z.number(),
		version: z.number(),
	}),
	loaderDeps: ({ search }) => search,
	loader: async ({ context, params, deps, location }) => {
		const character = await redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(characterQueryOptions(params.characterId)),
			location,
		);
		const me = await context.queryClient.ensureQueryData(meQueryOptions);
		if (character.user_id !== me.id) {
			throw redirect({ to: "/403", replace: true });
		}
		await Promise.all([
			context.queryClient.ensureQueryData(
				characterSheetMovePreviewQueryOptions(
					params.characterId,
					deps.sheet,
					deps.version,
				),
			),
			context.queryClient.ensureQueryData(
				characterSheetVersionsQueryOptions(deps.sheet),
			),
		]);
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { characterId } = Route.useParams();
	const { sheet: sheetId, version } = Route.useSearch();
	const { data: character } = useSuspenseQuery(characterQueryOptions(characterId));
	const { data: preview } = useSuspenseQuery(
		characterSheetMovePreviewQueryOptions(characterId, sheetId, version),
	);
	const { data: versions } = useSuspenseQuery(
		characterSheetVersionsQueryOptions(sheetId),
	);

	const isUpgrade = sheetId === character.character_sheet_id;
	// What changed on the way: since the character's version for an upgrade,
	// or the copy's whole history up to the target for a change.
	const changes = versions.filter(
		(sheetVersion) =>
			sheetVersion.number <= version &&
			(!isUpgrade || sheetVersion.number > character.version_number),
	);

	const queryClient = useQueryClient();
	const navigate = useNavigate();
	const moveMutation = useMutation({
		mutationFn: () =>
			moveCharacterSheet({
				character_ids: [characterId],
				character_sheet_id: sheetId,
				version,
			}),
		onSuccess: async () => {
			queryClient.invalidateQueries({ queryKey: ["characters"] });
			// Not this page's preview: refetched now, it'd fail, as the character
			// is already on that version.
			await Promise.all([
				queryClient.invalidateQueries({
					queryKey: characterQueryOptions(characterId).queryKey,
					exact: true,
				}),
				queryClient.invalidateQueries({
					queryKey: characterSheetMovesQueryOptions(characterId).queryKey,
					exact: true,
				}),
			]);
			navigate({ to: "/characters/$characterId/edit", params: { characterId } });
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div className={styles["character-sheet"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{character.name ?? character.label}
			</h1>

			<p>
				This is how {character.label} would look on{" "}
				<strong>
					{preview.name} v{version}
				</strong>
				{isUpgrade ? ` (currently v${character.version_number})` : ""}. Nothing changes
				until you {isUpgrade ? "upgrade" : "change sheets"}.
			</p>

			{preview.hidden_values.length > 0 ? (
				<p className="banner warning-banner">
					v{version} doesn't have{" "}
					{preview.hidden_values.length === 1 ? "this field" : "these fields"}:{" "}
					{preview.hidden_values.map((field) => field.label).join(", ")}. Their values
					stay saved on the character, but won't show.
				</p>
			) : null}

			<section className={previewStyles["changelog"]}>
				<div className={previewStyles["changelog-header"]}>
					<h2>Changes</h2>
					<Link to="/characters/sheets/$sheetId/changelog" params={{ sheetId }}>
						Full change log
					</Link>
				</div>
				<ol className={previewStyles["changelog-versions"]}>
					{changes.map((change) => (
						<li key={change.number}>
							<div className={previewStyles["changelog-meta"]}>
								<strong>v{change.number}</strong>
								<time dateTime={change.published_at}>
									{formatDate(change.published_at)}
								</time>
							</div>
							{change.changelog && !isContentEmpty(change.changelog) ? (
								<TiptapContent content={change.changelog} />
							) : (
								<p className={previewStyles["no-notes"]}>No notes for this version.</p>
							)}
						</li>
					))}
				</ol>
			</section>

			{moveMutation.error ? (
				<p className="banner error-banner">
					{moveMutation.error instanceof ApiError
						? moveMutation.error.errors.map((err) => err.detail).join(" ")
						: "Something went wrong. Please try again."}
				</p>
			) : null}

			<div className={previewStyles["actions"]}>
				<button
					type="button"
					className="skew-btn"
					onClick={() => moveMutation.mutate()}
					disabled={moveMutation.isPending}
				>
					{isUpgrade ? "Upgrade" : "Change Sheet"}
				</button>
				<Link
					to="/characters/$characterId/edit"
					params={{ characterId }}
					className="skew-btn"
				>
					Cancel
				</Link>
			</div>

			<SheetValuesProvider
				key={`${sheetId}:${version}`}
				mode="display"
				initialValues={character.values ?? {}}
			>
				<SheetRenderer schema={preview.layout} />
			</SheetValuesProvider>
		</div>
	);
}
