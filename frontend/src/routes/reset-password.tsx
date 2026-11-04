import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { checkResetToken, resetPassword } from "#/queries/password-reset";
import styles from "./reset-password.module.css";

export const Route = createFileRoute("/reset-password")({
	validateSearch: z.object({ token: z.string().optional() }),
	loaderDeps: ({ search }) => ({ token: search.token }),
	loader: async ({ deps }) => ({
		validToken: deps.token ? await checkResetToken(deps.token) : false,
	}),
	component: RouteComponent,
	errorComponent: CheckFailed,
});

function InvalidLink() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Reset Password
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p className="banner error-banner">
					This reset link is invalid or has expired.
				</p>
				<p>
					<Link to="/forgot-password">Request a new reset link</Link>
				</p>
			</div>
		</div>
	);
}

function CheckFailed() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Reset Password
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p className="banner error-banner">
					We couldn't check your reset link. Please try again in a moment.
				</p>
			</div>
		</div>
	);
}

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

function RouteComponent() {
	const { token } = Route.useSearch();
	const { validToken } = Route.useLoaderData();
	const navigate = useNavigate();
	const mutation = useMutation({ mutationFn: resetPassword });
	const [apiErrors, setApiErrors] = useState<string[]>([]);
	const [tokenRejected, setTokenRejected] = useState<boolean>(false);

	const form = useForm({
		defaultValues: {
			password: "",
			confirmPassword: "",
		},
		onSubmit: async ({ value }) => {
			if (!token) return;
			setApiErrors([]);
			try {
				await mutation.mutateAsync({
					token,
					password: value.password,
					confirm_password: value.confirmPassword,
				});
				navigate({ to: "/login", search: { reset: true } });
			} catch (exception) {
				if (exception instanceof ApiError) {
					if (exception.errors.some((e) => e.code === "invalid_token")) {
						setTokenRejected(true);
						return;
					}
					const details = exception.errors.map((e) => e.detail).filter(Boolean);
					if (details.length > 0) {
						setApiErrors(details);
						return;
					}
				}
				setApiErrors([
					"Something went wrong while resetting your password. Please try again.",
				]);
			}
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	if (!validToken || tokenRejected) return <InvalidLink />;

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Reset Password
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
				<p>Choose a new password for your account.</p>
				<form
					className={`auth-form ${styles["reset-password-form"]}`}
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
				>
					<form.Field
						name="password"
						validators={{
							onBlur: ({ value }) => {
								if (value.length < 8) return "Password must be at least 8 characters.";
								return undefined;
							},
						}}
					>
						{(field) => (
							<>
								<label htmlFor={field.name}>New Password</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="password"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										autoComplete="new-password"
										className={field.state.meta.isValid ? "" : "field-invalid"}
									/>
									<p className={styles["field-message"]}>
										Password must be at least 8 characters.
									</p>
								</div>
							</>
						)}
					</form.Field>
					<form.Field
						name="confirmPassword"
						validators={{
							onBlur: ({ value, fieldApi }) => {
								const password = fieldApi.form.getFieldValue("password");
								if (value && password && value !== password)
									return "Passwords do not match.";
								return undefined;
							},
						}}
					>
						{(field) => (
							<>
								<label htmlFor={field.name}>Confirm Password</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="password"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										autoComplete="new-password"
										className={field.state.meta.isValid ? "" : "field-invalid"}
									/>
									<p className={`${styles["field-message"]} ${styles["field-error"]}`}>
										<FieldError message={field.state.meta.errors[0]} />
									</p>
								</div>
							</>
						)}
					</form.Field>
					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div>
								<button
									type="submit"
									disabled={!canSubmit || mutation.isPending}
									className="skew-btn"
								>
									Reset Password
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>
		</div>
	);
}
