import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import clsx from "clsx";
import { useState } from "react";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import type { PM } from "#/queries/pms";
import { sendPM } from "#/queries/pms";
import { searchUserByUsername } from "#/queries/users";

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

export function PmForm({
	title,
	defaultUsername = "",
	defaultTitle = "",
	defaultMessage = emptyContent,
	replyToId,
	// Accepted but not rendered yet - reply's history view is a follow-up
	// (different format than the plain detail view).
	history: _history,
}: {
	title: string;
	defaultUsername?: string;
	defaultTitle?: string;
	defaultMessage?: JSONContent;
	replyToId?: number;
	history?: PM[];
}) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const mutation = useMutation({
		mutationFn: sendPM,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["pms"] });
		},
	});
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const form = useForm({
		defaultValues: {
			username: defaultUsername,
			title: defaultTitle,
			message: defaultMessage,
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			try {
				await mutation.mutateAsync({ ...value, reply_to_id: replyToId });
				navigate({ to: "/pms" });
			} catch (exception) {
				if (exception instanceof ApiError) {
					setApiErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{title}
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{apiErrors.length > 0 && (
					<div className="banner error-banner">
						<ul>
							{apiErrors.map((error) => (
								<li key={error}>{error}</li>
							))}
						</ul>
					</div>
				)}
				<form
					id="send-pm-form"
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
					className="grid-layout"
				>
					<form.Field
						name="username"
						validators={{
							onBlur: ({ value }) => (!value ? "Username is required." : undefined),
							onBlurAsync: async ({ value }) => {
								if (!value) return undefined;
								const user = await searchUserByUsername(value);
								return user ? undefined : "Invalid user";
							},
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name} className="push-down">
									Username:
								</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="text"
										maxLength={24}
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										autoComplete="off"
										className={clsx(
											"input-field",
											field.state.meta.isValid ? "" : "field-invalid",
										)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">
											<FieldError message={field.state.meta.errors[0]} />
										</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Field
						name="title"
						validators={{
							onBlur: ({ value }) => (!value ? "Title required!" : undefined),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name} className="push-down">
									Title:
								</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="text"
										maxLength={100}
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										className={clsx(
											"input-field",
											field.state.meta.isValid ? "" : "field-invalid",
										)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">
											<FieldError message={field.state.meta.errors[0]} />
										</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Field
						name="message"
						validators={{
							onBlur: ({ value }) =>
								isContentEmpty(value) ? "Message required!" : undefined,
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name} className="push-down">
									Message:
								</label>
								<div>
									<Editor
										id={field.name}
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(value) => field.handleChange(value)}
										className={field.state.meta.isValid ? "" : "field-invalid"}
									/>
									{field.state.meta.errors[0] && (
										<p className="error">
											<FieldError message={field.state.meta.errors[0]} />
										</p>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div className="is-container">
								<button
									type="submit"
									name="send"
									className="skew-btn"
									disabled={!canSubmit || mutation.isPending}
								>
									Send
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>
		</div>
	);
}
