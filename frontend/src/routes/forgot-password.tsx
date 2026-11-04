import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useHbMargined } from "#/lib/use-hb-margined";
import { requestPasswordReset } from "#/queries/password-reset";
import styles from "./forgot-password.module.css";

export const Route = createFileRoute("/forgot-password")({
	component: RouteComponent,
});

function RouteComponent() {
	const mutation = useMutation({ mutationFn: requestPasswordReset });
	const [sent, setSent] = useState<boolean>(false);
	const [failed, setFailed] = useState<boolean>(false);

	const form = useForm({
		defaultValues: {
			email: "",
		},
		onSubmit: async ({ value }) => {
			setSent(false);
			setFailed(false);
			try {
				await mutation.mutateAsync({ email: value.email });
				setSent(true);
			} catch (_exception) {
				setFailed(true);
			}
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Forgot Your Password?
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{sent && (
					<p className="banner success-banner">
						If an account with that email exists and is activated, we've sent a link to
						reset your password. The link works for 1 hour.
					</p>
				)}
				{failed && (
					<p className="banner error-banner">
						Something went wrong while sending your reset link. Please try again.
					</p>
				)}
				<p>
					Enter the email address of your account and we'll send you a link to reset
					your password.
				</p>
				<p>
					Please make sure <strong>no-reply@gamersplane.com</strong> is whitelisted on
					your email account. If you do not receive an email in your inbox, please check
					your spam folder.
				</p>
				<p>
					If you don't receive an email after trying this form, please{" "}
					<a href="mailto:contact@gamersplane.com">email us</a> and we'll help you out.
					Please try this form at least once.
				</p>
				<form
					className={`auth-form ${styles["forgot-password-form"]}`}
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
				>
					<form.Field
						name="email"
						validators={{
							onBlur: ({ value }) => {
								if (!value) return "Email is required.";
								if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
									return "Enter a valid email address.";
								return undefined;
							},
						}}
					>
						{(field) => (
							<>
								<label htmlFor={field.name}>Email</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="email"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										autoComplete="email"
										className={field.state.meta.isValid ? "" : "field-invalid"}
									/>
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
