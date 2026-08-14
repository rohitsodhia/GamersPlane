import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, notFound, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { requireAuth } from "#/lib/auth-route";
import { forumQueryOptions } from "#/queries/forums";
import { createThread } from "#/queries/threads";
import { PostForm } from "./-post-form";

export const Route = createFileRoute("/forums/new-thread/$forumId")({
	params: {
		parse: (params) => ({ forumId: Number(params.forumId) }),
	},
	beforeLoad: (ctx) => {
		if (!Number.isInteger(ctx.params.forumId) || ctx.params.forumId < 1) {
			throw notFound();
		}
		return requireAuth(ctx);
	},
	loader: async ({ context, params }) => {
		try {
			await context.queryClient.ensureQueryData(forumQueryOptions(params.forumId));
		} catch {
			throw notFound();
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const mutation = useMutation({
		mutationFn: createThread,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["threads", forumId] });
		},
	});

	return (
		<PostForm
			pageId="new-thread-page"
			headerTitle="New Thread"
			forum={forum}
			submitLabel="Create Thread"
			apiErrors={apiErrors}
			isSubmitting={mutation.isPending}
			onSubmit={async (value) => {
				setApiErrors([]);
				try {
					const thread = await mutation.mutateAsync({ forum_id: forumId, ...value });
					navigate({
						to: "/forums/thread/$threadId",
						params: { threadId: thread.id },
					});
				} catch (exception) {
					if (exception instanceof ApiError) {
						setApiErrors(exception.errors.map((e) => e.detail));
					}
				}
			}}
		/>
	);
}
