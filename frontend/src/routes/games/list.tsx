import { createFileRoute, Outlet } from "@tanstack/react-router";
import { z } from "zod";
import { ListFilters, listFiltersSearchSchema } from "#/components/ListFilters";
import { useHbMargined } from "#/lib/use-hb-margined";
import { systemsQueryOptions } from "#/queries/systems";

export const Route = createFileRoute("/games/list")({
	validateSearch: listFiltersSearchSchema.extend({
		page: z.number().optional(),
	}),
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				<i className="ra ra-d6" /> Browse Games
			</h1>

			<div style={{ marginInline: hbMargined.margin }}>
				<ListFilters filters={["search", "systems"]} idPrefix="games" />

				<Outlet />
			</div>
		</div>
	);
}
