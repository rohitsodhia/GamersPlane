import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { ApiError } from "#/lib/api";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { forumQueryOptions } from "#/queries/forums";
import { createThread } from "#/queries/threads";
import { Breadcrumbs } from "./-breadcrumbs";

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

export const Route = createFileRoute("/forums/new-thread/$forumId")({
	params: {
		parse: (params) => ({ forumId: Number(params.forumId) }),
	},
	beforeLoad: (ctx) => {
		if (!Number.isInteger(ctx.params.forumId) || ctx.params.forumId < 1) {
			throw notFound();
		}
		return requireAuth(ctx);
	},
	loader: async ({ context, params }) => {
		try {
			await context.queryClient.ensureQueryData(forumQueryOptions(params.forumId));
		} catch {
			throw notFound();
		}
	},
	component: RouteComponent,
});

const optionCheckboxes = [
	{ name: "options.sticky", label: "Sticky thread" },
	{ name: "options.locked", label: "Lock thread" },
	{ name: "options.allow_public_posting", label: "Allow public posting" },
	{ name: "options.allow_rolls", label: "Allow adding rolls to posts" },
	{ name: "options.allow_draws", label: "Allow adding draws to posts" },
] as const;

function RouteComponent() {
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const hbMarginedHeader = useHbMargined<HTMLHeadingElement>();
	const hbMarginedOptions = useHbMargined<HTMLHeadingElement>();

	const [apiErrors, setApiErrors] = useState<string[]>([]);
	const [optionsState, setOptionsState] = useState<"options" | "poll" | "dice_decks">(
		"options",
	);

	const mutation = useMutation({
		mutationFn: createThread,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["threads", forumId] });
		},
	});

	const form = useForm({
		defaultValues: {
			title: "",
			body: emptyContent,
			options: {
				sticky: false,
				locked: false,
				allow_public_posting: false,
				allow_rolls: false,
				allow_draws: false,
				discord_webhook: "",
			},
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			try {
				const thread = await mutation.mutateAsync({ forum_id: forumId, ...value });
				navigate({ to: "/thread/$threadId", params: { threadId: thread.id } });
			} catch (exception) {
				if (exception instanceof ApiError) {
					setApiErrors(exception.errors.map((e) => e.detail));
				}
			}
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
		<div id="new-thread-page">
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				New Thread
			</h1>
			<div style={{ marginInline: `${hbMarginedHeader.margin}px` }}>
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
					id="new-thread-form"
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
									disabled={!canSubmit || mutation.isPending}
								>
									Create Thread
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>

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
