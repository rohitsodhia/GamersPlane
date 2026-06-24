import { useForm } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { register } from "#/queries/register";

export const Route = createFileRoute("/register/")({ component: Register });

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

function Register() {
	const navigate = useNavigate();
	const mutation = useMutation({ mutationFn: register });
	const [registrationAPIErrors, setRegistrationAPIErrors] = useState<string[]>([]);

	const form = useForm({
		defaultValues: {
			username: "asaasdf",
			email: "asvwdf@gmail.com",
			password: "asdfasdf",
			confirmPassword: "asdfasdf",
		},
		onSubmit: async ({ value }) => {
			setRegistrationAPIErrors([]);
			try {
				const data = await mutation.mutateAsync({
					username: value.username,
					email: value.email,
					password: value.password,
				});

				if (data.registered) {
					navigate({ to: "/register/success" });
				}
			} catch (exception) {
				if (exception instanceof ApiError) {
					setRegistrationAPIErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	return (
		<div>
			<h1 className="headerbar">Create an Account</h1>
			{registrationAPIErrors.length > 0 && (
				<div className="hb-margined error-banner">
					<ul>
						{registrationAPIErrors.map((error) => (
							<li key={error}>{error}</li>
						))}
					</ul>
				</div>
			)}
			<form
				id="register-form"
				onSubmit={(e) => {
					e.preventDefault();
					form.handleSubmit();
				}}
			>
				<form.Field
					name="username"
					validators={{
						onBlur: ({ value }) => {
							if (value.length < 4) return "Username must be at least 4 characters.";
							if (value.length > 24) return "Username must be 24 characters or fewer.";
							return undefined;
						},
					}}
				>
					{(field) => (
						<>
							<label htmlFor={field.name}>Username</label>
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
									className={field.state.meta.isValid ? "" : "field-invalid"}
								/>
								<p
									className={clsx(
										"field-message",
										field.state.meta.errors.length ? "field-error" : "",
									)}
								>
									Username must be between 4 and 24 characters.
								</p>
							</div>
						</>
					)}
				</form.Field>

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
								<p className="field-message">
									<FieldError message={field.state.meta.errors[0]} />
								</p>
							</div>
						</>
					)}
				</form.Field>

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
							<label htmlFor={field.name}>Password</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="password"
									value={field.state.value}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
									autoComplete="off"
									className={field.state.meta.isValid ? "" : "field-invalid"}
								/>
								<p
									className={clsx(
										"field-message",
										field.state.meta.errors.length ? "field-error" : "",
									)}
								>
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
									autoComplete="off"
									className={field.state.meta.isValid ? "" : "field-invalid"}
								/>
								<p className="field-message">
									<FieldError message={field.state.meta.errors[0]} />
								</p>
							</div>
						</>
					)}
				</form.Field>

				<form.Subscribe selector={(state) => state.canSubmit}>
					{(canSubmit) => (
						<div>
							<button type="submit" disabled={!canSubmit} className="trap-btn">
								Register
							</button>
						</div>
					)}
				</form.Subscribe>
			</form>
		</div>
	);
}
