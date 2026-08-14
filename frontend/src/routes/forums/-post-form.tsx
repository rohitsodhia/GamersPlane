import { useForm } from "@tanstack/react-form";
import { Link } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import clsx from "clsx";
import { useState } from "react";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { useHbMargined } from "#/lib/use-hb-margined";
import type { ForumBreadcrumbs } from "#/queries/forums";
import { Breadcrumbs } from "./-breadcrumbs";

const optionCheckboxes = [
	{ name: "options.sticky", label: "Sticky thread" },
	{ name: "options.locked", label: "Lock thread" },
	{ name: "options.allow_public_posting", label: "Allow public posting" },
	{ name: "options.allow_rolls", label: "Allow adding rolls to posts" },
	{ name: "options.allow_draws", label: "Allow adding draws to posts" },
] as const;

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

export type PostFormValues = {
	title: string;
	body: JSONContent;
	options: {
		sticky: boolean;
		locked: boolean;
		allow_public_posting: boolean;
		allow_rolls: boolean;
		allow_draws: boolean;
		discord_webhook: string;
	};
};

export function PostForm({
	pageId,
	headerTitle,
	forum,
	defaultTitle = "",
	defaultBody = emptyContent,
	showThreadOptions = true,
	submitLabel,
	isSubmitting = false,
	apiErrors,
	onSubmit,
}: {
	pageId: string;
	headerTitle: string;
	forum: ForumBreadcrumbs;
	defaultTitle?: string;
	defaultBody?: JSONContent;
	showThreadOptions?: boolean;
	submitLabel: string;
	isSubmitting?: boolean;
	apiErrors: string[];
	onSubmit: (value: PostFormValues) => void | Promise<void>;
}) {
	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();
	const hbMarginedOptions = useHbMargined<HTMLHeadingElement>();

	const [optionsState, setOptionsState] = useState<"options" | "poll" | "dice_decks">(
		showThreadOptions ? "options" : "dice_decks",
	);

	const form = useForm({
		defaultValues: {
			title: defaultTitle,
			body: defaultBody,
			options: {
				sticky: false,
				locked: false,
				allow_public_posting: false,
				allow_rolls: false,
				allow_draws: false,
				discord_webhook: "",
			},
		} satisfies PostFormValues,
		onSubmit: async ({ value }) => {
			await onSubmit(value);
		},
	});

	function Options() {
		return (
			<div>
				{optionCheckboxes.map(({ name, label }) => (
					<form.Field key={name} name={name}>
						{(field) => (
							<div>
								<input
									type="checkbox"
									id={field.name}
									checked={field.state.value}
									onChange={(e) => field.handleChange(e.target.checked)}
								/>{" "}
								<label htmlFor={field.name}>{label}</label>
							</div>
						)}
					</form.Field>
				))}
				<hr />
				<form.Field name="options.discord_webhook">
					{(field) => (
						<>
							<label htmlFor={field.name}>Discord Webhook</label>
							<input
								type="text"
								id={field.name}
								value={field.state.value ?? ""}
								onBlur={field.handleBlur}
								onChange={(e) => field.handleChange(e.target.value)}
							/>
						</>
					)}
				</form.Field>
			</div>
		);
	}

	function Poll() {
		return <div>Poll</div>;
	}

	function DiceDecks() {
		return <div>Dice Decks</div>;
	}

	return (
		<div id={pageId} className="post-form">
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				{headerTitle}
			</h1>
			<div
				id="post-form-form-wrapper"
				style={{ marginInline: `${hbMarginedHeader.margin}px` }}
			>
				<Breadcrumbs forum={forum} />
				<div>
					Be sure to read and follow the{" "}
					<Link to="/community_guidelines">community guidelines</Link>.
				</div>

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
					id="post-form"
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
				>
					<form.Field
						name="title"
						validators={{
							onBlur: ({ value }) => (!value ? "Title required!" : undefined),
						}}
					>
						{(field) => (
							<>
								<label htmlFor={field.name}>Title:</label>
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
							</>
						)}
					</form.Field>

					<form.Field
						name="body"
						validators={{
							onBlur: ({ value }) =>
								isContentEmpty(value) ? "Message required!" : undefined,
						}}
					>
						{(field) => (
							<Editor
								id={field.name}
								value={field.state.value}
								onBlur={field.handleBlur}
								onChange={(value) => field.handleChange(value)}
								className={field.state.meta.isValid ? "" : "field-invalid"}
							/>
						)}
					</form.Field>

					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div>
								<button
									type="submit"
									name="submit"
									className="skew-btn"
									disabled={!canSubmit || isSubmitting}
								>
									{submitLabel}
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>

			{showThreadOptions && (
				<div className="controls-container">
					<div className="trapezoid">
						<button
							type="button"
							onClick={() => setOptionsState("options")}
							className={optionsState === "options" ? "current" : ""}
						>
							Options
						</button>
						<button
							type="button"
							onClick={() => setOptionsState("poll")}
							className={optionsState === "poll" ? "current" : ""}
						>
							Poll
						</button>
						<button
							type="button"
							onClick={() => setOptionsState("dice_decks")}
							className={optionsState === "dice_decks" ? "current" : ""}
						>
							Rolls and Decks
						</button>
					</div>
				</div>
			)}
			<h2 className="headerbar hb-dark" ref={hbMarginedOptions.ref}>
				Thread Options
			</h2>
			<div style={{ marginInline: `${hbMarginedOptions.margin}px` }}>
				{optionsState === "options" && <Options />}
				{optionsState === "poll" && <Poll />}
				{optionsState === "dice_decks" && <DiceDecks />}
			</div>
		</div>
	);
}
