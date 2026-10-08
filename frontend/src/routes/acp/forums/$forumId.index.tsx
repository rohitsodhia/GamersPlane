import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound, redirect } from "@tanstack/react-router";
import { requireForumModerator } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { forumQueryOptions } from "#/queries/forums";

export const Route = createFileRoute("/acp/forums/$forumId/")({
	loader: async ({ context, params }) => {
		await requireForumModerator({ context });
		const forum = await context.queryClient
			.ensureQueryData(forumQueryOptions(Number(params.forumId)))
			.catch(() => {
				throw notFound();
			});
		if (!forum.permissions.includes("forum_moderate")) {
			throw redirect({ to: "/acp/forums" });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(Number(forumId)));

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				{forum.id ? forum.title : "Forums"}
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>Moderation options are coming soon.</p>
				<Link to="/acp/forums">Back to forums</Link>
			</div>
		</div>
	);
}
