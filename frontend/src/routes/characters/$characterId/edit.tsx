import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { useState } from "react";
import { Select } from "#/components/Select";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import {
	type CharacterType,
	characterQueryOptions,
	updateCharacter,
} from "#/queries/character";
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

	const [label, setLabel] = useState(character.label);
	const [type, setType] = useState<CharacterType>(character.type);

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
					schema={sheet.layout}
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
