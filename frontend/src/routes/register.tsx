import { useForm } from "@tanstack/react-form";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/register")({ component: Register });

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <p className="field-error">{message}</p>;
}

function Register() {
	const form = useForm({
		defaultValues: {
			username: "",
			email: "",
			password: "",
			confirmPassword: "",
		},
		onSubmit: async ({ value }) => {
			console.log("Register form submitted:", value);
		},
	});

	return (
		<div>
			<h1 className="headerbar">Create an Account</h1>
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
							if (value.length < 4)
								return "Username must be at least 4 characters.";
							if (value.length > 24)
								return "Username must be 24 characters or fewer.";
							return undefined;
						},
					}}
				>
					{(field) => (
						<div className="form-field">
							<label htmlFor={field.name}>Username</label>
							<input
								id={field.name}
								name={field.name}
								type="text"
								maxLength={24}
								value={field.state.value}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
							/>
							<FieldError message={field.state.meta.errors[0]} />
						</div>
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
						<div className="form-field">
							<label htmlFor={field.name}>Email</label>
							<input
								id={field.name}
								name={field.name}
								type="email"
								value={field.state.value}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
							/>
							<FieldError message={field.state.meta.errors[0]} />
						</div>
					)}
				</form.Field>

				<form.Field
					name="password"
					validators={{
						onBlur: ({ value }) => {
							if (value.length < 8)
								return "Password must be at least 8 characters.";
							return undefined;
						},
					}}
				>
					{(field) => (
						<div className="form-field">
							<label htmlFor={field.name}>Password</label>
							<input
								id={field.name}
								name={field.name}
								type="password"
								value={field.state.value}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
							/>
							<FieldError message={field.state.meta.errors[0]} />
						</div>
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
						onChange: ({ value, fieldApi }) => {
							const password = fieldApi.form.getFieldValue("password");
							if (value && password && value !== password)
								return "Passwords do not match.";
							return undefined;
						},
					}}
				>
					{(field) => (
						<div className="form-field">
							<label htmlFor={field.name}>Confirm Password</label>
							<input
								id={field.name}
								name={field.name}
								type="password"
								value={field.state.value}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
							/>
							<FieldError message={field.state.meta.errors[0]} />
						</div>
					)}
				</form.Field>

				<form.Subscribe selector={(state) => state.canSubmit}>
					{(canSubmit) => (
						<button type="submit" disabled={!canSubmit} className="trapBtn">
							Register
						</button>
					)}
				</form.Subscribe>
			</form>
		</div>
	);
}
