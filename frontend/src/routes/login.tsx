import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { login } from "#/queries/login";
import { resendActivation } from "#/queries/register";
import { useAuthStore } from "#/stores/auth";
import styles from "./login.module.css";

const BLOCKED_REDIRECTS =
	/^\/register(\/|$)|^\/activate(\/|$)|^\/forgot-password(\/|$)|^\/reset-password(\/|$)/;

type LoginError =
	| { kind: "message"; message: string }
	| { kind: "not_activated"; email: string | undefined };

function toLoginError(exception: unknown): LoginError {
	if (exception instanceof ApiError) {
		const first = exception.errors[0];
		if (first?.code === "not_activated") {
			return { kind: "not_activated", email: exception.email };
		}
		if (first?.code === "invalid_user") {
			return {
				kind: "message",
				message: "Invalid username or password. Please try again.",
			};
		}
		if (first?.detail) {
			return { kind: "message", message: first.detail };
		}
	}
	return {
		kind: "message",
		message: "Something went wrong while logging in. Please try again.",
	};
}

function safeRedirect(redirect: string | undefined): string {
	if (redirect?.startsWith("/") && !BLOCKED_REDIRECTS.test(redirect)) {
		return redirect;
	}
	return "/";
}

export const Route = createFileRoute("/login")({
	validateSearch: z.object({
		redirect: z.string().optional(),
		reset: z.boolean().optional(),
	}),
	component: RouteComponent,
});

function RouteComponent() {
	const mutation = useMutation({ mutationFn: login });
	const resendMutation = useMutation({ mutationFn: resendActivation });
	const [loginError, setLoginError] = useState<LoginError | null>(null);
	const [resendState, setResendState] = useState<
		{ status: "sent"; email: string } | { status: "failed" } | null
	>(null);
	const setToken = useAuthStore((state) => state.setToken);
	const navigate = useNavigate();
	const { redirect, reset } = Route.useSearch();

	const resend = async (email: string) => {
		setResendState(null);
		try {
			await resendMutation.mutateAsync({ email });
			setResendState({ status: "sent", email });
		} catch (_exception) {
			setResendState({ status: "failed" });
		}
	};

	const form = useForm({
		defaultValues: {
			identifier: "",
			password: "",
		},
		onSubmit: async ({ value }) => {
			try {
				setLoginError(null);
				setResendState(null);
				const data = await mutation.mutateAsync({
					identifier: value.identifier,
					password: value.password,
				});

				if (data.logged_in) {
					setToken(data.jwt);
					navigate({ to: safeRedirect(redirect) });
				}
			} catch (exception) {
				setLoginError(toLoginError(exception));
			}
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div className={styles["login-page"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Login
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{reset && !loginError && (
					<p className="banner success-banner">
						Your password has been reset. You can now log in with your new password.
					</p>
				)}
				{loginError?.kind === "message" && (
					<p className="banner error-banner">{loginError.message}</p>
				)}
				{loginError?.kind === "not_activated" && (
					<div className="banner error-banner">
						<p>
							Your account hasn't been activated yet. Check your email for the
							activation link, or request a new one.
						</p>
						{resendState?.status === "sent" && (
							<p>We've sent a new activation email to {resendState.email}.</p>
						)}
						{resendState?.status === "failed" && (
							<p>We couldn't send the activation email. Please try again.</p>
						)}
						{loginError.email ? (
							<button
								type="button"
								className="skew-btn"
								disabled={resendMutation.isPending}
								onClick={() => resend(loginError.email as string)}
							>
								Resend activation email
							</button>
						) : (
							<Link to="/register/resend">Resend activation email</Link>
						)}
					</div>
				)}
				<form
					className={`auth-form ${styles["login-form"]}`}
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
								<button type="submit" disabled={!canSubmit} className="skew-btn">
									Login
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
				<p className={styles["login-links"]}>
					<Link to="/forgot-password">Forgot your password?</Link>
					<span>
						Don't have an account? <Link to="/register">Register</Link>
					</span>
				</p>
			</div>
		</div>
	);
}
