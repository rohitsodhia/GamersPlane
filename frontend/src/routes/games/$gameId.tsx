import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/games/$gameId")({
	component: RouteComponent,
});

function RouteComponent() {
	const { gameId } = Route.useParams();
	return <div>Game {gameId}</div>;
}
