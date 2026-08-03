import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { ApiError } from "#/lib/api";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { sendPM } from "#/queries/pms";

export const Route = createFileRoute("/pms/send")({
	beforeLoad: requireAuth,
	component: RouteComponent,
});

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

// TODO: swap for a real username-lookup endpoint once one exists on the API.
async function checkUsernameExists(_username: string): Promise<boolean> {
	return true;
}

function RouteComponent() {
	const navigate = useNavigate();
	const mutation = useMutation({ mutationFn: sendPM });
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const form = useForm({
		defaultValues: {
			username: "",
			title: "",
			message: emptyContent,
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			try {
				await mutation.mutateAsync(value);
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
				New Private Message
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
								const exists = await checkUsernameExists(value);
								return exists ? undefined : "Invalid user";
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
									<p
										className={clsx(
											"field-message",
											field.state.meta.errors.length ? "field-error" : "",
										)}
									>
										<FieldError message={field.state.meta.errors[0]} />
									</p>
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
									<p
										className={clsx(
											"field-message",
											field.state.meta.errors.length ? "field-error" : "",
										)}
									>
										<FieldError message={field.state.meta.errors[0]} />
									</p>
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
									<p
										className={clsx(
											"field-message",
											field.state.meta.errors.length ? "field-error" : "",
										)}
									>
										<FieldError message={field.state.meta.errors[0]} />
									</p>
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
									className="trap-btn"
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
