import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { resendActivation } from "#/queries/register";

export const Route = createFileRoute("/register/resend")({
	component: RouteComponent,
});

function RouteComponent() {
	const mutation = useMutation({ mutationFn: resendActivation });
	const [resendAPISuccess, setResendAPISuccess] = useState<boolean>(true);

	const form = useForm({
		defaultValues: {
			email: "",
		},
		onSubmit: async ({ value }) => {
			try {
				const data = await mutation.mutateAsync({
					email: value.email,
				});

				if (data.registered) {
					setResendAPISuccess(true);
				}
			} catch (exception) {}
		},
	});

	return (
		<div>
			<h1 className="headerbar">Resend Activation Email</h1>
			<div className="hb-margined">
				{resendAPISuccess && (
					<p className="banner success-banner">
						An email has been sent to you with a link to activate your account.
					</p>
				)}
				<p>
					Please make sure <strong>contact@gamersplane.com</strong> is whitelisted on
					your email account. If you do not recieve an email in your inbox, please check
					your spam folder.
				</p>
				<p>
					If you don't recieve an email after trying this form, please{" "}
					<a href="mailto:contact@gamersplane.com">email us</a> and we'll help you out.
					Please try this form at least once.
				</p>
				<form
					id="resend-activation-form"
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
									<p className="field-message"></p>
								</div>
							</>
						)}
					</form.Field>
					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div>
								<button type="submit" disabled={!canSubmit} className="trap-btn">
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
