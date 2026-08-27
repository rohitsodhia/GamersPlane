import { createFileRoute } from "@tanstack/react-router";
import { systemsQueryOptions } from "#/queries/systems";
import { GameForm } from "./-game-form";

export const Route = createFileRoute("/games/new")({
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
	},
	component: RouteComponent,
});

function RouteComponent() {
	return <GameForm title="New Game" />;
}
