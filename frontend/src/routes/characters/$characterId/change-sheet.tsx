import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Select } from "#/components/Select";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type CharacterSheetMoves,
	characterQueryOptions,
	characterSheetMovesQueryOptions,
} from "#/queries/character";
import { meQueryOptions } from "#/queries/me";
import styles from "./change-sheet.module.css";

// The copies of a character's sheet it can change to. Picking one goes to the
// shared preview page, where the move is confirmed.
export const Route = createFileRoute("/characters/$characterId/change-sheet")({
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
		await context.queryClient.ensureQueryData(
			characterSheetMovesQueryOptions(params.characterId),
		);
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { characterId } = Route.useParams();
	const { data: character } = useSuspenseQuery(characterQueryOptions(characterId));
	const { data: sheetMoves } = useSuspenseQuery(
		characterSheetMovesQueryOptions(characterId),
	);
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<div style={{ marginLeft: hbMargined.margin }}>
				<Link to="/characters/$characterId/edit" params={{ characterId }}>
					Back to {character.label}
				</Link>
			</div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Change Sheet
			</h1>

			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>
					{character.sheet_deleted
						? `${character.character_sheet.name}, the sheet ${character.label} was built on, has been deleted. `
						: ""}
					{sheetMoves.copies.length === 0
						? "There are no copies of this sheet to change to."
						: `${character.label} can change to any of these copies of ${character.character_sheet.name}. You'll see a preview before anything changes.`}
				</p>

				{sheetMoves.copies.length > 0 ? (
					<ul className={styles["copies"]}>
						{sheetMoves.copies.map((copy) => (
							<CopyRow key={copy.id} characterId={characterId} copy={copy} />
						))}
					</ul>
				) : null}
			</div>
		</div>
	);
}

function CopyRow({
	characterId,
	copy,
}: {
	characterId: number;
	copy: CharacterSheetMoves["copies"][number];
}) {
	const navigate = useNavigate();
	const { data: me } = useSuspenseQuery(meQueryOptions);
	const isMine = copy.creator.id === me.id;
	// Version numbers run 1..latest with no gaps (only publishing assigns
	// one), so the options don't need their own fetch. Newest first, and
	// picked by default.
	const versionOptions = Array.from(
		{ length: copy.latest_version_number },
		(_, index) => {
			const number = copy.latest_version_number - index;
			return { id: String(number), name: `v${number}` };
		},
	);
	const [version, setVersion] = useState(String(copy.latest_version_number));

	return (
		<li className={styles["copy"]}>
			<div>
				<Link to="/characters/sheets/$sheetId" params={{ sheetId: copy.id }}>
					{copy.name}
				</Link>
				{isMine ? null : (
					<>
						{" "}
						by{" "}
						<Link to="/user/$userId" params={{ userId: copy.creator.id }}>
							{copy.creator.username}
						</Link>
					</>
				)}
			</div>
			<div className={styles["copy-actions"]}>
				<span id={`copy-version-label-${copy.id}`}>Version</span>
				<Select
					id={`copy-version-${copy.id}`}
					ariaLabelledBy={`copy-version-label-${copy.id}`}
					items={versionOptions}
					getId={(option) => option.id}
					getLabel={(option) => option.name}
					selectedId={version}
					onChange={setVersion}
				/>
				<button
					type="button"
					className="skew-btn"
					onClick={() =>
						navigate({
							to: "/characters/$characterId/sheet-preview",
							params: { characterId },
							search: {
								sheet: copy.id,
								version: Number(version),
								from: "change-sheet",
							},
						})
					}
				>
					Preview
				</button>
			</div>
		</li>
	);
}
