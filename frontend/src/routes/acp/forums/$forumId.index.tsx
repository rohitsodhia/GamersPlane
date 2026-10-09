import { createFileRoute, redirect } from "@tanstack/react-router";
import { forumQueryOptions, hasEditableDetails } from "#/queries/forums";

export const Route = createFileRoute("/acp/forums/$forumId/")({
	loader: async ({ context, params }) => {
		const forum = await context.queryClient.ensureQueryData(
			forumQueryOptions(params.forumId),
		);
		throw redirect({
			to: hasEditableDetails(forum)
				? "/acp/forums/$forumId/details"
				: "/acp/forums/$forumId/subforums",
			params,
		});
	},
});
