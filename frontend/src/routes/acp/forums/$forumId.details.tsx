import { useForm } from "@tanstack/react-form";
import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { useState } from "react";
import { FadeOut } from "#/components/FadeOut";
import { ApiError } from "#/lib/api";
import { useFlash } from "#/lib/use-flash";
import {
	forumQueryOptions,
	hasEditableDetails,
	PROTECTED_FORUM_IDS,
	updateForum,
} from "#/queries/forums";
import styles from "../acp.module.css";

export const Route = createFileRoute("/acp/forums/$forumId/details")({
	loader: async ({ context, params }) => {
		const forum = await context.queryClient.ensureQueryData(
			forumQueryOptions(params.forumId),
		);
		if (!hasEditableDetails(forum)) {
			throw redirect({ to: "/acp/forums/$forumId/subforums", params });
		}
	},
	component: RouteComponent,
});

function errorList(exception: unknown): string[] {
	if (exception instanceof ApiError) return exception.errors.map((e) => e.detail);
	return ["Something went wrong."];
}

function RouteComponent() {
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	const queryClient = useQueryClient();

	const titleLocked = PROTECTED_FORUM_IDS.includes(forum.id);
	// Categories are headings, so only forums show a description.
	const hasDescription = forum.forum_type === "f";

	const [errors, setErrors] = useState<string[]>([]);
	const [saved, flashSaved] = useFlash();
	const form = useForm({
		defaultValues: {
			title: forum.title,
			description: forum.description ?? "",
		},
		onSubmit: async ({ value }) => {
			setErrors([]);
			if (!titleLocked && value.title.trim().length < 3) {
				setErrors(["The title must be at least 3 characters."]);
				return;
			}
			try {
				await updateForum(forumId, {
					...(titleLocked ? {} : { title: value.title }),
					...(hasDescription ? { description: value.description } : {}),
				});
				await queryClient.invalidateQueries({ queryKey: ["forums"] });
				flashSaved();
			} catch (exception) {
				setErrors(errorList(exception));
			}
		},
	});

	return (
		<div>
			{errors.length > 0 && (
				<div className="banner error-banner">
					<ul>
						{errors.map((error) => (
							<li key={error}>{error}</li>
						))}
					</ul>
				</div>
			)}
			<form
				className={styles["forum-details-form"]}
				onSubmit={(e) => {
					e.preventDefault();
					form.handleSubmit();
				}}
			>
				<form.Field name="title">
					{(field) => (
						<div>
							<label htmlFor={field.name}>Title</label>
							<input
								id={field.name}
								name={field.name}
								type="text"
								maxLength={200}
								value={field.state.value}
								disabled={titleLocked}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
							/>
						</div>
					)}
				</form.Field>
				{hasDescription && (
					<form.Field name="description">
						{(field) => (
							<div>
								<label htmlFor={field.name}>Description</label>
								<textarea
									id={field.name}
									name={field.name}
									value={field.state.value}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						)}
					</form.Field>
				)}
				<div className={styles["save-row"]}>
					<form.Subscribe selector={(state) => state.isSubmitting}>
						{(isSubmitting) => (
							<button type="submit" className="skew-btn" disabled={isSubmitting}>
								Save
							</button>
						)}
					</form.Subscribe>
					<FadeOut active={saved}>Saved</FadeOut>
				</div>
			</form>
		</div>
	);
}
