import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { characterQueryOptions, updateCharacter } from "#/queries/character";
import { SheetRenderer } from "../sheets/-components/SheetRenderer";
import { SheetValuesProvider, useSheetStore } from "../sheets/-components/sheet-values";
import type { SheetSchema } from "../sheets/-components/types";
import AvatarPopover from "./-avatar-popover";
import styles from "./character.module.css";

export const Route = createFileRoute("/characters/$characterId/edit")({
	params: {
		parse: (params) => ({ characterId: Number(params.characterId) }),
	},
	loader: ({ context, params, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(characterQueryOptions(params.characterId)),
			location,
		),
	component: RouteComponent,
});

function RouteComponent() {
	const { characterId } = Route.useParams();
	const { data: character } = useSuspenseQuery(characterQueryOptions(characterId));
	const { character_sheet: sheet } = character;
	const primaryAvatar = character.avatars.find((avatar) => avatar.is_primary);

	// Remount when switching characters so the value store re-seeds from the
	// newly loaded `values`.
	return (
		<div className={styles["character-sheet"]}>
			<h1 className="headerbar">{character.name ?? character.label}</h1>

			<div className={styles["sheet-logo"]}>
				<img
					src={`/images/logos/${sheet.system.id}.png`}
					alt={sheet.system.name}
					title={sheet.system.name}
				/>
			</div>

			<div className={styles["avatar-wrapper"]}>
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
				<CharacterSheetForm characterId={characterId} schema={sheet.layout} />
			</SheetValuesProvider>
		</div>
	);
}

function CharacterSheetForm({
	characterId,
	schema,
}: {
	characterId: number;
	schema: SheetSchema;
}) {
	const store = useSheetStore();
	const queryClient = useQueryClient();
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const mutation = useMutation({
		mutationFn: (values: ReturnType<typeof store.snapshot>) =>
			updateCharacter(characterId, values),
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
