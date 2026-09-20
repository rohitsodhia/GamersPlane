import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import clsx from "clsx";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { characterQueryOptions } from "#/queries/character";
import { meQueryOptions } from "#/queries/me";
import { SheetRenderer } from "../sheets/-components/SheetRenderer";
import { SheetValuesProvider } from "../sheets/-components/sheet-values";
import styles from "./character.module.css";

export const Route = createFileRoute("/characters/$characterId/")({
	params: {
		parse: (params) => ({ characterId: Number(params.characterId) }),
	},
	loader: async ({ context, params, location }) => {
		const character = await redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(characterQueryOptions(params.characterId)),
			location,
		);
		const me = await context.queryClient.ensureQueryData(meQueryOptions);
		// Non-library characters are visible only to their owner.
		if (!character.in_library && character.user_id !== me.id) {
			throw redirect({ to: "/403", replace: true });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { characterId } = Route.useParams();
	const { data: character } = useSuspenseQuery(characterQueryOptions(characterId));
	const { character_sheet: sheet } = character;

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div className={styles["character-sheet"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{character.name ?? character.label}
			</h1>
			<div className={clsx("controls-container", styles["top-links"])}>
				<div
					className="trapezoid red-trapezoid upside-down"
					style={{ marginRight: hbMargined.margin }}
				>
					<Link to="/characters/$characterId/edit" params={{ characterId }}>
						Edit
					</Link>
					<button type="button">
						<img
							src="/images/icons/bookmark_off.png"
							title="Favorite Character"
							alt="Favorite Character"
						/>
					</button>
				</div>
			</div>

			<div className={styles["sheet-logo"]}>
				<img
					src={`/images/logos/${sheet.system.id}.png`}
					alt={sheet.system.name}
					title={sheet.system.name}
				/>
			</div>

			<div className={styles["character-meta"]}>
				<div>
					<span>Label</span>
					<span>{character.label}</span>
				</div>
				<div>
					<span>Type</span>
					<span>{character.type.toLocaleUpperCase()}</span>
				</div>
			</div>

			<SheetValuesProvider
				key={characterId}
				mode="display"
				initialValues={character.values ?? {}}
			>
				<SheetRenderer schema={sheet.layout} />
			</SheetValuesProvider>
		</div>
	);
}
