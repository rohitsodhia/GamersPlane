import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/characters/sheets/$sheetId/changelog")({
	params: {
		parse: (params) => ({ sheetId: Number(params.sheetId) }),
	},
	component: RouteComponent,
});

function RouteComponent() {
	return <div>Hello "/characters/sheets/$sheetId/changelog"!</div>;
}
