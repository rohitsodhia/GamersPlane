import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, notFound } from "@tanstack/react-router";
import { z } from "zod";
import { gameDetailsQueryOptions } from "#/queries/game";
import { systemsQueryOptions } from "#/queries/systems";
import { useGameBarGame } from "#/stores/game-bar";
import { GameForm } from "../-game-form";

export const Route = createFileRoute("/games/$gameId/edit")({
	params: {
		parse: (params) => ({ gameId: Number(params.gameId) }),
	},
	validateSearch: z.object({ backgroundError: z.string().optional() }),
	beforeLoad: ({ params }) => {
		if (!Number.isInteger(params.gameId) || params.gameId < 1) throw notFound();
	},
	loader: async ({ context, params }) => {
		try {
			await Promise.all([
				context.queryClient.ensureQueryData(gameDetailsQueryOptions(params.gameId)),
				context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true })),
			]);
		} catch {
			throw notFound();
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { gameId } = Route.useParams();
	const { backgroundError } = Route.useSearch();
	const { data: game } = useSuspenseQuery(gameDetailsQueryOptions(gameId));
	useGameBarGame(gameId);

	return <GameForm title="Edit Game" game={game} initialError={backgroundError} />;
}
