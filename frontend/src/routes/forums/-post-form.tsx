import { useForm, useStore } from "@tanstack/react-form";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import clsx from "clsx";
import { useState } from "react";
import { Checkbox } from "#/components/Checkbox";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type ForumBreadcrumbs,
	type ForumPermission,
	forumDecksQueryOptions,
} from "#/queries/forums";
import type {
	NewDrawInput,
	NewRollInput,
	PostRoll,
	RollVisibilityInput,
} from "#/queries/posts";
import type { PollData, PollInput, ThreadOptions } from "#/queries/threads";
import {
	type AttachmentAccess,
	type Attachments,
	attachmentAccess,
	attachmentErrors,
	buildAttachmentPayload,
	emptyAttachments,
} from "./-attachment-rows";
import { Breadcrumbs } from "./-breadcrumbs";
import { PollEditor, pollHasErrors } from "./-poll-editor";
import { type PollState, pollPayload, pollStateFromData } from "./-poll-editor-state";
import { PostAttachmentsEditor } from "./-post-attachments";
import styles from "./-post-form.module.css";
import { changedRollVisibility, initialVisibility } from "./-post-rolls";
import { RollVisibilityEditor } from "./-roll-visibility-editor";
import type { ThreadOptionsValues } from "./-thread-options";

// Each option needs a forum permission to set; mirrors OPTION_VERBS in the API.
const optionCheckboxes = [
	{ name: "options.sticky", label: "Sticky thread", permission: "forum_moderate" },
	{ name: "options.locked", label: "Lock thread", permission: "forum_moderate" },
	{
		name: "options.allow_public_posting",
		label: "Allow public posting",
		permission: "forum_moderate",
	},
	{
		name: "options.allow_rolls",
		label: "Allow adding rolls to posts",
		permission: "forum_add_rolls",
	},
	{
		name: "options.allow_draws",
		label: "Allow adding draws to posts",
		permission: "forum_add_draws",
	},
] as const satisfies readonly {
	name: string;
	label: string;
	permission: ForumPermission;
}[];

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

type PostFormFields = {
	title: string;
	body: JSONContent;
	options: ThreadOptionsValues;
	// Only meaningful when editing; a minor edit skips the Discord ping.
	minorEdit: boolean;
};

export const noOptions: ThreadOptionsValues = {
	sticky: false,
	locked: false,
	allow_public_posting: false,
	allow_rolls: false,
	allow_draws: false,
	discord_webhook: "",
};

export type PostFormValues = PostFormFields & {
	rolls: NewRollInput[];
	draws: NewDrawInput[];
	// Only the existing rolls whose visibility changed.
	rollVisibility: RollVisibilityInput[];
	// What the request's `poll` key holds; undefined when the poll is unchanged (or
	// there is none) and the key should be left out.
	poll: PollInput | null | undefined;
};

export function PostForm({
	pageId,
	headerTitle,
	forum,
	defaultTitle = "",
	defaultBody = emptyContent,
	showThreadOptions = true,
	defaultOptions = noOptions,
	showWebhook = true,
	permissions = [],
	threadOptions,
	canAddAttachments = true,
	existingRolls = [],
	existingPoll = null,
	showMinorEdit = false,
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
	// What the options start as (editing a thread's first post).
	defaultOptions?: ThreadOptionsValues;
	// Hides the webhook field even for moderators; only its author can read it.
	showWebhook?: boolean;
	// The user's permissions on the forum; decides which thread options show, and
	// whether rolls and draws can be added.
	permissions?: ForumPermission[];
	// The existing thread's options, when they aren't being set here (editing).
	threadOptions?: Pick<ThreadOptions, "allow_rolls" | "allow_draws">;
	// False when the user can't add rolls or draws to this post (not its author).
	canAddAttachments?: boolean;
	// The rolls already on the post (editing); their visibility can be changed here.
	existingRolls?: PostRoll[];
	// The thread's poll, when editing its first post.
	existingPoll?: PollData | null;
	// Shows the "minor edit" checkbox (editing only).
	showMinorEdit?: boolean;
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

	const [attachments, setAttachments] = useState<Attachments>(emptyAttachments);
	const [showAttachmentErrors, setShowAttachmentErrors] = useState(false);
	const [rollVisibility, setRollVisibility] = useState(() =>
		initialVisibility(existingRolls),
	);
	const hbMarginedVisibility = useHbMargined<HTMLHeadingElement>();

	// The poll as loaded, to tell whether it changed; `poll` is null for none.
	const [initialPoll] = useState<PollState | null>(() =>
		existingPoll ? pollStateFromData(existingPoll) : null,
	);
	const [poll, setPoll] = useState<PollState | null>(initialPoll);
	const [showPollErrors, setShowPollErrors] = useState(false);

	const form = useForm({
		defaultValues: {
			title: defaultTitle,
			body: defaultBody,
			options: defaultOptions,
			// An edit is assumed minor unless the author unticks it.
			minorEdit: true as boolean,
		} satisfies PostFormFields,
		onSubmit: async ({ value }) => {
			const pollProblems = canAddPoll && pollHasErrors(poll);
			const attachmentProblems = Object.keys(attachmentRowErrors).length > 0;
			if (pollProblems || attachmentProblems) {
				setShowPollErrors(pollProblems);
				setShowAttachmentErrors(attachmentProblems);
				setOptionsState(pollProblems ? "poll" : "dice_decks");
				return;
			}
			await onSubmit({
				...value,
				...buildAttachmentPayload(attachments, attachmentAccessNow),
				rollVisibility: changedRollVisibility(existingRolls, rollVisibility),
				poll: canAddPoll ? pollPayload(initialPoll, poll) : undefined,
			});
		},
	});

	const canSet = (permission: ForumPermission) =>
		permissions.includes(permission) || permissions.includes("forum_moderate");
	// The poll belongs to the thread, so it's set wherever the thread options are.
	const canAddPoll = showThreadOptions && canSet("forum_add_poll");
	const pollInvalid = canAddPoll && pollHasErrors(poll);

	// A new thread's options are the form's own; an edit follows the thread's.
	const formOptions = useStore(form.store, (state) => state.values.options);
	const attachmentOptions = showThreadOptions
		? formOptions
		: (threadOptions ?? { allow_rolls: false, allow_draws: false });
	const attachmentAccessNow: AttachmentAccess = canAddAttachments
		? attachmentAccess(attachmentOptions, permissions)
		: { rolls: false, draws: false };
	const { data: decksData } = useQuery({
		...forumDecksQueryOptions(forum.id),
		enabled: attachmentAccessNow.draws,
	});
	const decks = attachmentAccessNow.draws ? (decksData ?? []) : [];
	const attachmentRowErrors = attachmentErrors(attachments, attachmentAccessNow, decks);
	const hasAttachmentUI =
		attachmentAccessNow.rolls || (attachmentAccessNow.draws && decks.length > 0);

	// Inline JSX rather than components: a component defined in this body would be
	// a new type every render and remount (losing focus) on each keystroke.
	const optionsPanel = (
		<div>
			{optionCheckboxes
				.filter(({ permission }) => canSet(permission))
				.map(({ name, label }) => (
					<form.Field key={name} name={name}>
						{(field) => (
							<div className={styles["option-checkbox"]}>
								<Checkbox
									id={field.name}
									checked={field.state.value}
									onChange={(checked) => field.handleChange(checked)}
								/>
								<label htmlFor={field.name}>{label}</label>
							</div>
						)}
					</form.Field>
				))}
			{showWebhook && canSet("forum_moderate") && (
				<>
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
				</>
			)}
		</div>
	);

	// Why the Rolls and Decks tab is empty, when it is.
	function attachmentsHint() {
		const canRoll =
			permissions.includes("forum_add_rolls") || permissions.includes("forum_moderate");
		const canDraw =
			permissions.includes("forum_add_draws") || permissions.includes("forum_moderate");
		if (!canRoll && !canDraw) return "You can't add rolls or draws in this forum.";
		if (!attachmentAccessNow.rolls && !attachmentAccessNow.draws)
			return 'Turn on "Allow adding rolls to posts" or "Allow adding draws to posts" under Options to add them.';
		return "There are no decks you can draw from here.";
	}

	return (
		<div id={pageId} className={styles["post-form"]}>
			<h1 className="headerbar" ref={hbMarginedHeader.ref}>
				{headerTitle}
			</h1>
			<div
				className={styles["post-form-form-wrapper"]}
				style={{ marginInline: `${hbMarginedHeader.margin}px` }}
			>
				<Breadcrumbs forum={forum} />
				<div>
					Be sure to read and follow the{" "}
					<Link to="/community-guidelines">community guidelines</Link>.
				</div>

				{(apiErrors.length > 0 ||
					(showPollErrors && pollInvalid) ||
					(showAttachmentErrors && Object.keys(attachmentRowErrors).length > 0)) && (
					<div className="banner error-banner">
						<ul>
							{showPollErrors && pollInvalid && (
								<li>Fix the problems under Poll before posting.</li>
							)}
							{showAttachmentErrors && Object.keys(attachmentRowErrors).length > 0 && (
								<li>Fix the problems under Rolls and Decks before posting.</li>
							)}
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
											styles["input-field"],
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
								{showMinorEdit && (
									<form.Field name="minorEdit">
										{(field) => (
											<div className={styles["option-checkbox"]}>
												<Checkbox
													id={field.name}
													checked={field.state.value}
													onChange={(checked) => field.handleChange(checked)}
												/>
												<label htmlFor={field.name}>This is a minor edit</label>
											</div>
										)}
									</form.Field>
								)}
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
						{canAddPoll && (
							<button
								type="button"
								onClick={() => setOptionsState("poll")}
								className={optionsState === "poll" ? "current" : ""}
							>
								Poll
							</button>
						)}
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
			{(showThreadOptions || hasAttachmentUI) && (
				<>
					<h2 className="headerbar hb-dark has-topper" ref={hbMarginedOptions.ref}>
						{showThreadOptions ? "Thread Options" : "Rolls and Decks"}
					</h2>
					<div style={{ marginInline: `${hbMarginedOptions.margin}px` }}>
						{optionsState === "options" && optionsPanel}
						{optionsState === "poll" && canAddPoll && (
							<PollEditor value={poll} onChange={setPoll} showErrors={showPollErrors} />
						)}
						{optionsState === "dice_decks" &&
							(hasAttachmentUI ? (
								<PostAttachmentsEditor
									value={attachments}
									onChange={setAttachments}
									access={attachmentAccessNow}
									decks={decks}
									showErrors={showAttachmentErrors}
								/>
							) : (
								<div>{attachmentsHint()}</div>
							))}
					</div>
				</>
			)}
			{/* Belongs with Rolls and Decks; that's always the tab on a reply. */}
			{existingRolls.length > 0 && optionsState === "dice_decks" && (
				<>
					<h2 className="headerbar hb-dark has-topper" ref={hbMarginedVisibility.ref}>
						Roll Visibility
					</h2>
					<div style={{ marginInline: `${hbMarginedVisibility.margin}px` }}>
						<RollVisibilityEditor
							rolls={existingRolls}
							value={rollVisibility}
							onChange={setRollVisibility}
						/>
					</div>
				</>
			)}
		</div>
	);
}
