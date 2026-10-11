import { useForm } from "@tanstack/react-form";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { type ReactNode, useEffect, useState } from "react";
import { z } from "zod";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { sendContact } from "#/queries/contact";
import { meFullQueryOptions } from "#/queries/me";
import { useAuthStore } from "#/stores/auth";
import styles from "./contact.module.css";

export const Route = createFileRoute("/contact")({ component: RouteComponent });

// Mirrors the API's limits (api/src/app/contact/schemas.py)
const NAME_MAX = 50;
const EMAIL_MAX = 100;
const USERNAME_MAX = 50;
const SUBJECT_MAX = 100;
const MESSAGE_MAX = 5000;

const requiredText = (label: string, max: number) =>
	z
		.string()
		.trim()
		.min(1, `${label} is required.`)
		.max(max, `${label} must be ${max} characters or fewer.`);

const nameSchema = requiredText("Name", NAME_MAX);
const emailSchema = z
	.string()
	.trim()
	.min(1, "Email is required.")
	.max(EMAIL_MAX, `Email must be ${EMAIL_MAX} characters or fewer.`)
	.pipe(z.email("Enter a valid email address."));
const usernameSchema = z
	.string()
	.trim()
	.max(USERNAME_MAX, `Username must be ${USERNAME_MAX} characters or fewer.`);
const subjectSchema = requiredText("Subject", SUBJECT_MAX);
const messageSchema = requiredText("Message", MESSAGE_MAX);

const RATE_LIMITED_MESSAGE =
	"You've sent a few messages recently. Please wait a while before sending another.";
const GENERIC_ERROR_MESSAGE =
	"Something went wrong sending your message. Please try again.";

function FieldBox({
	id,
	label,
	error,
	children,
}: {
	id: string;
	label: string;
	error: string | undefined;
	children: ReactNode;
}) {
	return (
		<div className={styles["field"]}>
			<label htmlFor={id}>{label}</label>
			{children}
			{error && <p className={styles["field-error"]}>{error}</p>}
		</div>
	);
}

function RouteComponent() {
	const token = useAuthStore((state) => state.token);
	const { data: me } = useQuery({ ...meFullQueryOptions, enabled: !!token });
	const loggedIn = !!token && !!me;

	const mutation = useMutation({ mutationFn: sendContact });
	const [sent, setSent] = useState(false);
	const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
	const [bannerError, setBannerError] = useState<string | null>(null);

	const form = useForm({
		defaultValues: {
			name: "",
			email: "",
			username: "",
			subject: "",
			message: "",
			website: "",
		},
		onSubmit: async ({ value }) => {
			setFieldErrors({});
			setBannerError(null);
			try {
				await mutation.mutateAsync({
					...value,
					// The API ignores it for logged-in users
					username: loggedIn ? "" : value.username,
				});
				setSent(true);
			} catch (exception) {
				if (exception instanceof ApiError) {
					if (exception.status === 429) {
						setBannerError(RATE_LIMITED_MESSAGE);
						return;
					}
					const withField = exception.errors.filter((e) => e.field);
					if (withField.length > 0) {
						setFieldErrors(
							Object.fromEntries(withField.map((e) => [e.field as string, e.detail])),
						);
						return;
					}
				}
				setBannerError(GENERIC_ERROR_MESSAGE);
			}
		},
	});

	// Prefill the email from the account once it loads, without clobbering typing
	useEffect(() => {
		if (me && !form.getFieldValue("email") && !form.getFieldMeta("email")?.isTouched) {
			form.setFieldValue("email", me.email);
		}
	}, [me, form]);

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	const errorFor = (
		field: { state: { meta: { errors: unknown[] } } },
		name: string,
	) => {
		const local = field.state.meta.errors[0] as { message?: string } | undefined;
		return local?.message ?? fieldErrors[name];
	};

	return (
		<div className={styles["contact-page"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Contact Us
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{sent ? (
					<div className={styles["thanks"]}>
						<p>
							<strong>Thanks for reaching out.</strong>
						</p>
						<p>
							Thank you for contacting us. We'll get back to you as soon as possible!
						</p>
					</div>
				) : (
					<>
						{bannerError && <p className="banner error-banner">{bannerError}</p>}
						<p>
							{loggedIn
								? "All fields are required."
								: 'All fields except "username" are required.'}
						</p>
						<form
							className={styles["contact-form"]}
							onSubmit={(e) => {
								e.preventDefault();
								form.handleSubmit();
							}}
						>
							<form.Field name="name" validators={{ onBlur: nameSchema }}>
								{(field) => {
									const error = errorFor(field, "name");
									return (
										<FieldBox id={field.name} label="Name" error={error}>
											<input
												id={field.name}
												name={field.name}
												type="text"
												maxLength={NAME_MAX}
												value={field.state.value}
												onBlur={field.handleBlur}
												onChange={(e) => field.handleChange(e.target.value)}
												autoComplete="name"
												className={error ? styles["field-invalid"] : ""}
											/>
										</FieldBox>
									);
								}}
							</form.Field>

							<form.Field name="email" validators={{ onBlur: emailSchema }}>
								{(field) => {
									const error = errorFor(field, "email");
									return (
										<FieldBox id={field.name} label="Email" error={error}>
											<input
												id={field.name}
												name={field.name}
												type="email"
												maxLength={EMAIL_MAX}
												value={field.state.value}
												onBlur={field.handleBlur}
												onChange={(e) => field.handleChange(e.target.value)}
												autoComplete="email"
												className={error ? styles["field-invalid"] : ""}
											/>
										</FieldBox>
									);
								}}
							</form.Field>

							{!loggedIn && (
								<form.Field name="username" validators={{ onBlur: usernameSchema }}>
									{(field) => {
										const error = errorFor(field, "username");
										return (
											<FieldBox id={field.name} label="Username" error={error}>
												<input
													id={field.name}
													name={field.name}
													type="text"
													maxLength={USERNAME_MAX}
													value={field.state.value}
													onBlur={field.handleBlur}
													onChange={(e) => field.handleChange(e.target.value)}
													autoComplete="username"
													className={error ? styles["field-invalid"] : ""}
												/>
											</FieldBox>
										);
									}}
								</form.Field>
							)}

							<form.Field name="subject" validators={{ onBlur: subjectSchema }}>
								{(field) => {
									const error = errorFor(field, "subject");
									return (
										<FieldBox id={field.name} label="Subject" error={error}>
											<input
												id={field.name}
												name={field.name}
												type="text"
												maxLength={SUBJECT_MAX}
												value={field.state.value}
												onBlur={field.handleBlur}
												onChange={(e) => field.handleChange(e.target.value)}
												autoComplete="off"
												className={error ? styles["field-invalid"] : ""}
											/>
										</FieldBox>
									);
								}}
							</form.Field>

							<form.Field name="message" validators={{ onBlur: messageSchema }}>
								{(field) => {
									const error = errorFor(field, "message");
									return (
										<FieldBox id={field.name} label="Message" error={error}>
											<textarea
												id={field.name}
												name={field.name}
												maxLength={MESSAGE_MAX}
												value={field.state.value}
												onBlur={field.handleBlur}
												onChange={(e) => field.handleChange(e.target.value)}
												className={error ? styles["field-invalid"] : ""}
											/>
										</FieldBox>
									);
								}}
							</form.Field>

							{/* Honeypot: off-screen and skipped by keyboards and screen readers */}
							<form.Field name="website">
								{(field) => (
									<div className={styles["honeypot"]} aria-hidden="true">
										<label htmlFor={field.name}>Leave this field empty</label>
										<input
											id={field.name}
											name={field.name}
											type="text"
											tabIndex={-1}
											autoComplete="off"
											value={field.state.value}
											onChange={(e) => field.handleChange(e.target.value)}
										/>
									</div>
								)}
							</form.Field>

							<form.Subscribe selector={(state) => state.canSubmit}>
								{(canSubmit) => (
									<div className={styles["actions"]}>
										<button
											type="submit"
											disabled={!canSubmit || mutation.isPending}
											className="skew-btn"
										>
											Submit
										</button>
									</div>
								)}
							</form.Subscribe>
						</form>
					</>
				)}
			</div>
		</div>
	);
}
