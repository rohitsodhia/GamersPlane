import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, notFound, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { requireAuth } from "#/lib/auth-route";
import { forumQueryOptions } from "#/queries/forums";
import { editPost, postQueryOptions } from "#/queries/posts";
import { PostForm } from "./-post-form";

export const Route = createFileRoute("/forums/edit-post/$postId")({
	params: {
		parse: (params) => ({ postId: Number(params.postId) }),
	},
	beforeLoad: (ctx) => {
		if (!Number.isInteger(ctx.params.postId) || ctx.params.postId < 1) {
			throw notFound();
		}
		return requireAuth(ctx);
	},
	loader: async ({ context, params }) => {
		try {
			const post = await context.queryClient.ensureQueryData(
				postQueryOptions(params.postId),
			);
			await context.queryClient.ensureQueryData(forumQueryOptions(post.forum_id));
		} catch {
			throw notFound();
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { postId } = Route.useParams();
	const { data: post } = useSuspenseQuery(postQueryOptions(postId));
	const { data: forum } = useSuspenseQuery(forumQueryOptions(post.forum_id));
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const mutation = useMutation({
		mutationFn: editPost,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["posts", post.thread_id] });
		},
	});

	return (
		<PostForm
			pageId="edit-post-page"
			headerTitle={`Edit Post - ${post.title}`}
			forum={forum}
			defaultTitle={post.title}
			defaultBody={post.body}
			showThreadOptions={false}
			submitLabel="Save Changes"
			apiErrors={apiErrors}
			isSubmitting={mutation.isPending}
			onSubmit={async (value) => {
				setApiErrors([]);
				try {
					await mutation.mutateAsync({
						post_id: postId,
						title: value.title,
						body: value.body,
					});
					navigate({
						to: "/forums/thread/$threadId",
						params: { threadId: post.thread_id },
						search: { page: post.page },
						hash: `post-${postId}`,
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
