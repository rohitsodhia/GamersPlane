import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { login } from "#/queries/login";
import { useAuthStore } from "#/stores/auth";

const BLOCKED_REDIRECTS = /^\/register(\/|$)|^\/activate(\/|$)/;

function safeRedirect(redirect: string | undefined): string {
	if (redirect?.startsWith("/") && !BLOCKED_REDIRECTS.test(redirect)) {
		return redirect;
	}
	return "/";
}

export const Route = createFileRoute("/login")({
	validateSearch: z.object({ redirect: z.string().optional() }),
	component: RouteComponent,
});

function RouteComponent() {
	const mutation = useMutation({ mutationFn: login });
	const [apiErrors, setAPIErrors] = useState<boolean>(false);
	const setToken = useAuthStore((state) => state.setToken);
	const navigate = useNavigate();
	const { redirect } = Route.useSearch();

	const form = useForm({
		defaultValues: {
			identifier: "",
			password: "",
		},
		onSubmit: async ({ value }) => {
			try {
				setAPIErrors(false);
				const data = await mutation.mutateAsync({
					identifier: value.identifier,
					password: value.password,
				});

				if (data.logged_in) {
					setToken(data.jwt);
					navigate({ to: safeRedirect(redirect) });
				}
			} catch (exception) {
				setAPIErrors(true);
			}
		},
	});

	return (
		<div id="login-page">
			<h1 className="headerbar">Login</h1>
			<div className="hb-margined">
				{apiErrors && (
					<p className="banner error-banner">
						Invalid username or password. Please try again.
					</p>
				)}
				<form
					id="login-form"
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
				>
					<form.Field
						name="identifier"
						validators={{
							onBlur: ({ value }) => {
								if (!value) return "Identifier is required.";
								return undefined;
							},
						}}
					>
						{(field) => (
							<>
								<label htmlFor={field.name}>Email/Username</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="input"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										autoComplete="yes"
										className={field.state.meta.isValid ? "" : "field-invalid"}
									/>
								</div>
							</>
						)}
					</form.Field>
					<form.Field
						name="password"
						validators={{
							onBlur: ({ value }) => {
								if (!value) return "Password is required.";
								return undefined;
							},
						}}
					>
						{(field) => (
							<>
								<label htmlFor={field.name}>Password</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="password"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										className={field.state.meta.isValid ? "" : "field-invalid"}
									/>
								</div>
							</>
						)}
					</form.Field>
					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div>
								<button type="submit" disabled={!canSubmit} className="trap-btn">
									Login
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>
		</div>
	);
}
