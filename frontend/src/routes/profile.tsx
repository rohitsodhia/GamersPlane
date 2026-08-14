import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	deleteUserAvatar,
	meFullQueryOptions,
	refreshMe,
	updateUserAvatar,
	updateUserPassword,
	updateUserSettings,
} from "#/queries/me";

export const Route = createFileRoute("/profile")({
	beforeLoad: requireAuth,
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(meFullQueryOptions),
			location,
		),
	component: RouteComponent,
});

function RouteComponent() {
	const { data: me } = useSuspenseQuery(meFullQueryOptions);
	const queryClient = useQueryClient();
	const [showProfileSuccess, setShowProfileSuccess] = useState(false);
	const [showSecuritySuccess, setShowSecuritySuccess] = useState(false);

	const updateSettingsMutation = useMutation({ mutationFn: updateUserSettings });
	const updateAvatarMutation = useMutation({ mutationFn: updateUserAvatar });
	const deleteAvatarMutation = useMutation({ mutationFn: deleteUserAvatar });
	const updatePasswordMutation = useMutation({ mutationFn: updateUserPassword });

	const profileSettingsForm = useForm({
		defaultValues: {
			avatarFile: undefined as File | undefined,
			deleteAvatar: false,
			pronouns: me.pronouns ?? undefined,
			birthday: me.birthday ?? undefined,
			showAge: me.showAge ?? undefined,
			location: me.location ?? undefined,
			pmMail: me.pmMail ?? undefined,
			newGameMail: me.newGameMail ?? undefined,
			gmMail: me.gmMail ?? undefined,
			postSide: me.postSide,
			lookingForAGame: me.lookingForAGame ? "1" : "0",
			games: me.games ?? "",
		},
		onSubmit: async ({ value }) => {
			const { avatarFile, deleteAvatar, lookingForAGame, ...profile } = value;

			await updateSettingsMutation.mutateAsync({
				...profile,
				lookingForAGame: lookingForAGame === "1",
			});
			if (avatarFile) {
				await updateAvatarMutation.mutateAsync(avatarFile);
			} else if (deleteAvatar) {
				await deleteAvatarMutation.mutateAsync();
			}

			await refreshMe(queryClient);

			setShowProfileSuccess(true);
			setTimeout(() => setShowProfileSuccess(false), 3000);
		},
	});

	const securityForm = useForm({
		defaultValues: {
			oldPassword: "",
			password: "",
			confirmPassword: "",
		},
		onSubmit: async ({ value, formApi }) => {
			await updatePasswordMutation.mutateAsync(value);

			formApi.reset();

			setShowSecuritySuccess(true);
			setTimeout(() => setShowSecuritySuccess(false), 3000);
		},
	});

	const profileHbMargined = useHbMargined<HTMLHeadingElement>();
	const securityHbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div id="edit-profile-page">
			<h1 className="headerbar">Edit Settings</h1>
			<h2 className="headerbar" ref={profileHbMargined.ref}>
				Profile
			</h2>
			<form
				id="profile-settings-form"
				onSubmit={(e) => {
					e.preventDefault();
					profileSettingsForm.handleSubmit();
				}}
				className="grid-layout"
				style={{ marginInline: `${profileHbMargined.margin}px` }}
			>
				<div>
					<div>User Since</div>
					<div>
						{new Intl.DateTimeFormat("en-US", {
							dateStyle: "long",
							timeStyle: "short",
						}).format(me.joinDate)}
					</div>
				</div>
				<div id="edit-settings_avatar">
					<label htmlFor="edit-settings_avatar-file">Avatar</label>
					<div>
						<div id="edit-settings_avatar-disp">
							<img src={me?.avatar} alt="Your avatar" />
							<profileSettingsForm.Field name="deleteAvatar">
								{(field) => (
									<div>
										<input
											id="edit-settings_avatar-delete"
											type="checkbox"
											checked={field.state.value}
											onChange={(e) => field.handleChange(e.target.checked)}
										/>
										<label htmlFor="edit-settings_avatar-delete">Delete avatar</label>
									</div>
								)}
							</profileSettingsForm.Field>
						</div>
						<profileSettingsForm.Field name="avatarFile">
							{(field) => (
								<input
									id="edit-settings_avatar-file"
									type="file"
									accept="image/*"
									onChange={(e) => field.handleChange(e.target.files?.[0] ?? undefined)}
								/>
							)}
						</profileSettingsForm.Field>
						<p>
							Only images at least 150px by 150px will be accepted, with a maximum file
							size of 1MB.
						</p>
						<p>The images may be shrunk for GP use.</p>
					</div>
				</div>

				<profileSettingsForm.Field name="pronouns">
					{(field) => (
						<div>
							<label htmlFor={field.name} className="center-vertically">
								Pronouns
							</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="text"
									value={field.state.value}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="birthday">
					{(field) => (
						<div>
							<label htmlFor={field.name} className="center-vertically">
								Birthday
							</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="date"
									value={field.state.value}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="showAge">
					{(field) => (
						<div>
							<label htmlFor={field.name}>Show Age?</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="checkbox"
									checked={field.state.value}
									onChange={(e) => field.handleChange(e.target.checked)}
								/>
								<span className="explanation">
									Only your age will be shown, not your full birthday.
								</span>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="location">
					{(field) => (
						<div>
							<label htmlFor={field.name} className="center-vertically">
								Location
							</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="text"
									value={field.state.value}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="pmMail">
					{(field) => (
						<div>
							<div>Receive PM emails?</div>
							<div>
								<input
									id="edit-settings_pm-mail-yes"
									type="radio"
									name={field.name}
									checked={field.state.value === true}
									onChange={() => field.handleChange(true)}
								/>
								<label htmlFor="edit-settings_pm-mail-yes">Yes</label>
								<input
									id="edit-settings_pm-mail-no"
									type="radio"
									name={field.name}
									checked={field.state.value === false}
									onChange={() => field.handleChange(false)}
								/>
								<label htmlFor="edit-settings_pm-mail-no">No</label>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="newGameMail">
					{(field) => (
						<div>
							<div>Receive new game emails?</div>
							<div>
								<input
									id="edit-settings_new-game-mail-yes"
									type="radio"
									name={field.name}
									checked={field.state.value === true}
									onChange={() => field.handleChange(true)}
								/>
								<label htmlFor="edit-settings_new-game-mail-yes">Yes</label>
								<input
									id="edit-settings_new-game-mail-no"
									type="radio"
									name={field.name}
									checked={field.state.value === false}
									onChange={() => field.handleChange(false)}
								/>
								<label htmlFor="edit-settings_new-game-mail-no">No</label>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="gmMail">
					{(field) => (
						<div>
							<div>Receive GM emails?</div>
							<div>
								<input
									id="edit-settings_gm-mail-yes"
									type="radio"
									name={field.name}
									checked={field.state.value === true}
									onChange={() => field.handleChange(true)}
								/>
								<label htmlFor="edit-settings_gm-mail-yes">Yes</label>
								<input
									id="edit-settings_gm-mail-no"
									type="radio"
									name={field.name}
									checked={field.state.value === false}
									onChange={() => field.handleChange(false)}
								/>
								<label htmlFor="edit-settings_gm-mail-no">No</label>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="postSide">
					{(field) => (
						<div>
							<div>Post side</div>
							<div>
								<input
									id="edit-settings_post-side-right"
									type="radio"
									name={field.name}
									value="r"
									checked={field.state.value === "r"}
									onChange={() => field.handleChange("r")}
								/>
								<label htmlFor="edit-settings_post-side-right">Right</label>
								<input
									id="edit-settings_post-side-left"
									type="radio"
									name={field.name}
									value="l"
									checked={field.state.value === "l"}
									onChange={() => field.handleChange("l")}
								/>
								<label htmlFor="edit-settings_post-side-left">Left</label>
								<input
									id="edit-settings_post-side-conversation"
									type="radio"
									name={field.name}
									value="c"
									checked={field.state.value === "c"}
									onChange={() => field.handleChange("c")}
								/>
								<label htmlFor="edit-settings_post-side-conversation">
									Conversation
								</label>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="lookingForAGame">
					{(field) => (
						<div>
							<label htmlFor="lookingForAGame" className="center-vertically">
								Looking for a game?
							</label>
							<div>
								<select
									id={field.name}
									name={field.name}
									value={field.state.value}
									onChange={(e) => field.handleChange(e.target.value)}
								>
									<option value="0">My game interests</option>
									<option value="1">I'm looking for a game</option>
								</select>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Field name="games">
					{(field) => (
						<div>
							<label htmlFor="games">What games are you into?</label>
							<div>
								<textarea
									id={field.name}
									name={field.name}
									value={field.state.value}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						</div>
					)}
				</profileSettingsForm.Field>

				<profileSettingsForm.Subscribe selector={(state) => state.canSubmit}>
					{(canSubmit) => (
						<div className="is-container center">
							<button type="submit" disabled={!canSubmit} className="skew-btn">
								Save
							</button>
						</div>
					)}
				</profileSettingsForm.Subscribe>
				<div className="is-container">
					<div
						className={`banner success-banner ${showProfileSuccess ? "is-visible" : ""}`}
					>
						Settings saved
					</div>
					<output aria-live="polite" className="visually-hidden">
						{showProfileSuccess ? "Settings saved" : ""}
					</output>{" "}
				</div>
			</form>

			<h2 className="headerbar hb-dark" ref={securityHbMargined.ref}>
				Security
			</h2>
			<form
				id="security-form"
				onSubmit={(e) => {
					e.preventDefault();
					securityForm.handleSubmit();
				}}
				className="grid-layout"
				style={{ marginInline: `${securityHbMargined.margin}px` }}
			>
				<div className="span-two-col">
					If you're looking to change your username or email, please email
					contact@gamersplane.com; I've had to temporarily disable the automatic
					functionality.
				</div>
				<securityForm.Field name="oldPassword">
					{(field) => (
						<div>
							<label htmlFor={field.name} className="center-vertically">
								Old Password
							</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="password"
									maxLength={32}
									value={field.state.value}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
								{updatePasswordMutation.error instanceof ApiError &&
									updatePasswordMutation.error.errors.some(
										(err) => err.code === "invalid_old_password",
									) && <div className="error">Your old password is wrong</div>}
							</div>
						</div>
					)}
				</securityForm.Field>
				<securityForm.Field
					name="password"
					validators={{
						onChange: ({ value }) =>
							value.length > 0 && value.length < 8
								? "Password too short"
								: value.length > 32
									? "Password too long"
									: undefined,
					}}
				>
					{(field) => (
						<div>
							<label htmlFor={field.name} className="push-down">
								Change Password
							</label>
							<div>
								<input
									id={field.name}
									name={field.name}
									type="password"
									maxLength={32}
									value={field.state.value}
									onChange={(e) => field.handleChange(e.target.value)}
									autoComplete="new-password"
								/>
								<div className="explanation">
									Password must be between 8-32 characters
								</div>
								{field.state.meta.errors.length > 0 && (
									<div className="error">{field.state.meta.errors.join(", ")}</div>
								)}
							</div>
						</div>
					)}
				</securityForm.Field>
				<securityForm.Field
					name="confirmPassword"
					validators={{
						onBlurListenTo: ["password"],
						onBlur: ({ value, fieldApi }) =>
							value.length > 0 && value !== fieldApi.form.getFieldValue("password")
								? "Passwords don't match"
								: undefined,
					}}
				>
					{(field) => (
						<>
							<div>
								<label htmlFor={field.name} className="push-down">
									Confirm Password
								</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="password"
										maxLength={32}
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										autoComplete="new-password"
									/>
									{field.state.meta.errors.length > 0 && (
										<div className="error">{field.state.meta.errors.join(", ")}</div>
									)}
								</div>
							</div>
						</>
					)}
				</securityForm.Field>
				<securityForm.Subscribe selector={(state) => state.canSubmit}>
					{(canSubmit) => (
						<div className="is-container center">
							<button type="submit" disabled={!canSubmit} className="skew-btn">
								Save
							</button>
						</div>
					)}
				</securityForm.Subscribe>
				<div className="is-container">
					<div
						className={`banner success-banner ${showSecuritySuccess ? "is-visible" : ""}`}
					>
						Settings saved
					</div>
					<output aria-live="polite" className="visually-hidden">
						{showSecuritySuccess ? "Settings saved" : ""}
					</output>{" "}
				</div>
			</form>
		</div>
	);
}
