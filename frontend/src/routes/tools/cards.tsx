import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/tools/cards")({
	component: RouteComponent,
});

function RouteComponent() {
	return <div>Hello "/tools/cards"!</div>;
}
