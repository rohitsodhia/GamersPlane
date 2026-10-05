import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import { DismissibleBanner } from "#/components/DismissibleBanner";
import { Select } from "#/components/Select";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type CharacterType,
	characterQueryOptions,
	updateCharacter,
} from "#/queries/character";
import { copyCharacterSheet, restoreCharacterSheet } from "#/queries/characterSheet";
import { meQueryOptions } from "#/queries/me";
import { SheetRenderer } from "../sheets/-components/SheetRenderer";
import { SheetValuesProvider, useSheetStore } from "../sheets/-components/sheet-values";
import type { SheetSchema } from "../sheets/-components/types";
import AvatarPopover from "./-avatar-popover";
import styles from "./character.module.css";

const TYPE_OPTIONS: { id: CharacterType; name: string }[] = [
	{ id: "pc", name: "PC" },
	{ id: "npc", name: "NPC" },
];

export const Route = createFileRoute("/characters/$characterId/edit")({
	params: {
		parse: (params) => ({ characterId: Number(params.characterId) }),
	},
	loader: async ({ context, params, location }) => {
		const character = await redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(characterQueryOptions(params.characterId)),
			location,
		);
		const me = await context.queryClient.ensureQueryData(meQueryOptions);
		if (character.user_id !== me.id) {
			throw redirect({ to: "/403", replace: true });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { characterId } = Route.useParams();
	const { data: character } = useSuspenseQuery(characterQueryOptions(characterId));
	const { character_sheet: sheet } = character;
	const primaryAvatar = character.avatars.find((avatar) => avatar.is_primary);

	const { data: me } = useSuspenseQuery(meQueryOptions);
	const queryClient = useQueryClient();

	const [label, setLabel] = useState(character.label);
	const [type, setType] = useState<CharacterType>(character.type);

	// Your own deleted sheet is restored rather than copied. Copying is for a
	// sheet you can't maintain yourself: someone else's, even once they've
	// deleted it (the API lets you copy it since you have a character on it).
	const ownsSheet = sheet.creator.id === me.id;
	const canRestoreSheet = character.sheet_deleted && ownsSheet;
	const canCopySheet = !ownsSheet;
	const copyMutation = useMutation({
		// The version this character is pinned to, so the copy matches it.
		mutationFn: () =>
			copyCharacterSheet(character.character_sheet_id, character.version_number),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["characterSheets"] });
		},
	});
	const restoreMutation = useMutation({
		mutationFn: () => restoreCharacterSheet(character.character_sheet_id),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["characterSheets"] });
			queryClient.invalidateQueries({ queryKey: ["characterSheet"] });
			// Clears `sheet_deleted`, which hides the notice and the button.
			queryClient.invalidateQueries({
				queryKey: characterQueryOptions(characterId).queryKey,
			});
		},
	});
	const sheetActionError = copyMutation.error ?? restoreMutation.error;

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	// Remount when switching characters so the value store re-seeds from the
	// newly loaded `values`.
	return (
		<div className={styles["character-sheet"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{character.name ?? character.label}
			</h1>
			{canCopySheet || canRestoreSheet ? (
				<div className={clsx("controls-container", styles["top-links"])}>
					<div
						className="trapezoid red-trapezoid upside-down"
						style={{ marginRight: hbMargined.margin }}
					>
						{canRestoreSheet ? (
							<button
								type="button"
								onClick={() => restoreMutation.mutate()}
								disabled={restoreMutation.isPending}
							>
								Restore Sheet
							</button>
						) : (
							<button
								type="button"
								onClick={() => copyMutation.mutate()}
								disabled={copyMutation.isPending}
							>
								Copy Sheet
							</button>
						)}
					</div>
				</div>
			) : null}

			{copyMutation.isSuccess ? (
				<p className="banner success-banner">
					Sheet copied as a draft.{" "}
					<Link
						to="/characters/sheets/$sheetId"
						params={{ sheetId: copyMutation.data.id }}
					>
						Open the copy
					</Link>
				</p>
			) : null}
			{restoreMutation.isSuccess ? (
				<p className="banner success-banner">Sheet restored.</p>
			) : null}
			{sheetActionError ? (
				<p className="banner error-banner">
					{sheetActionError instanceof ApiError
						? sheetActionError.errors.map((err) => err.detail).join(" ")
						: "Something went wrong. Please try again."}
				</p>
			) : null}

			{character.sheet_deleted ? (
				<DismissibleBanner
					storageKey={`deleted-sheet:${characterId}`}
					className="warning-banner"
				>
					{canRestoreSheet
						? "You deleted the sheet this character was built on. You can restore it if you would like to use it again."
						: "The sheet this character was built on has been deleted. You can copy it if you would like to make updates."}
				</DismissibleBanner>
			) : null}

			<div className={styles["sheet-logo"]}>
				<img
					src={`/images/logos/${sheet.system.id}.png`}
					alt={sheet.system.name}
					title={sheet.system.name}
				/>
			</div>

			<div className={styles["avatar-wrapper"]}>
				<div className={styles["character-meta"]}>
					<div>
						<label htmlFor="character-label">Label</label>
						<input
							id="character-label"
							type="text"
							value={label}
							onChange={(e) => setLabel(e.target.value)}
						/>
					</div>
					<div>
						<span id="character-type-label">Type</span>
						<Select
							id="character-type"
							ariaLabelledBy="character-type-label"
							items={TYPE_OPTIONS}
							getId={(option) => option.id}
							getLabel={(option) => option.name}
							selectedId={type}
							onChange={(id) => setType(id as CharacterType)}
						/>
					</div>
				</div>

				<div>
					<button type="button" popoverTarget="character-avatar-popover">
						Edit Avatar
					</button>{" "}
					(Avatar Set:{" "}
					{primaryAvatar ? (
						<img
							src="/images/icons/green_check.png"
							title="Avatar set"
							alt="Avatar set"
						/>
					) : (
						<img
							src="/images/icons/cross.png"
							title="No avatar set"
							alt="No avatar set"
						/>
					)}
					)
				</div>
			</div>
			<AvatarPopover
				id="character-avatar-popover"
				characterId={characterId}
				avatars={character.avatars}
			/>
			<SheetValuesProvider
				key={characterId}
				mode="edit"
				initialValues={character.values ?? {}}
			>
				<CharacterSheetForm
					characterId={characterId}
					schema={character.layout}
					label={label}
					type={type}
				/>
			</SheetValuesProvider>
		</div>
	);
}

function CharacterSheetForm({
	characterId,
	schema,
	label,
	type,
}: {
	characterId: number;
	schema: SheetSchema;
	label: string;
	type: CharacterType;
}) {
	const store = useSheetStore();
	const queryClient = useQueryClient();
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const mutation = useMutation({
		mutationFn: (values: ReturnType<typeof store.snapshot>) =>
			updateCharacter(characterId, { label, type, values }),
		onSuccess: (character) => {
			queryClient.setQueryData(characterQueryOptions(characterId).queryKey, character);
		},
	});

	return (
		<form
			onSubmit={async (e) => {
				e.preventDefault();
				setApiErrors([]);
				try {
					await mutation.mutateAsync(store.snapshot());
				} catch (exception) {
					if (exception instanceof ApiError) {
						setApiErrors(exception.errors.map((err) => err.detail));
					}
				}
			}}
		>
			<SheetRenderer schema={schema} />

			{apiErrors.length > 0 && (
				<div className="banner error-banner">
					<ul>
						{apiErrors.map((error) => (
							<li key={error}>{error}</li>
						))}
					</ul>
				</div>
			)}

			<div className={styles["btn-wrapper"]}>
				<button type="submit" className="skew-btn" disabled={mutation.isPending}>
					Save
				</button>
			</div>
		</form>
	);
}
