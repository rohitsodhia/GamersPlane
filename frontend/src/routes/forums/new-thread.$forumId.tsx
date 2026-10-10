import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, notFound, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { requireAuth } from "#/lib/auth-route";
import { type ForumPermission, forumQueryOptions } from "#/queries/forums";
import { createThread } from "#/queries/threads";
import { noOptions, PostForm } from "./-post-form";

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
			// Draws change the decks' remaining cards.
			queryClient.invalidateQueries({ queryKey: ["forums", forumId, "decks"] });
		},
	});

	// Game threads start with rolls and draws on, where the user can set them.
	const canSet = (permission: ForumPermission) =>
		forum.permissions.includes(permission) ||
		forum.permissions.includes("forum_moderate");
	const isGameForum = forum.game_id != null;
	const defaultOptions = {
		...noOptions,
		allow_rolls: isGameForum && canSet("forum_add_rolls"),
		allow_draws: isGameForum && canSet("forum_add_draws"),
	};

	return (
		<PostForm
			pageId="new-thread-page"
			headerTitle="New Thread"
			forum={forum}
			defaultOptions={defaultOptions}
			permissions={forum.permissions}
			submitLabel="Create Thread"
			apiErrors={apiErrors}
			isSubmitting={mutation.isPending}
			onSubmit={async (value) => {
				setApiErrors([]);
				try {
					// A new thread has no poll to remove, so `poll` is never null here.
					const { minorEdit: _minorEdit, poll, ...fields } = value;
					const thread = await mutation.mutateAsync({
						forum_id: forumId,
						...fields,
						poll: poll ?? undefined,
					});
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
