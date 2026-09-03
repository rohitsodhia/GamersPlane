import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/characters/sheets/$sheetId")({
	params: {
		parse: (params) => ({ sheetId: Number(params.sheetId) }),
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { sheetId } = Route.useParams();

	return <div>Hello "/characters/sheets/{sheetId}"!</div>;
}
