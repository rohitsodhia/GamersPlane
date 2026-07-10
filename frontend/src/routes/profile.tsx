import { useForm } from "@tanstack/react-form";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { requireAuth } from "#/lib/auth-route";
import {
	deleteUserAvatar,
	meFullQueryOptions,
	refreshMe,
	updateUserAvatar,
	updateUserSettings,
} from "#/queries/me";

export const Route = createFileRoute("/profile")({
	beforeLoad: requireAuth,
	loader: ({ context }) => context.queryClient.ensureQueryData(meFullQueryOptions),
	component: RouteComponent,
});

function RouteComponent() {
	const { data: me } = useSuspenseQuery(meFullQueryOptions);
	const queryClient = useQueryClient();

	const updateSettingsMutation = useMutation({ mutationFn: updateUserSettings });
	const updateAvatarMutation = useMutation({ mutationFn: updateUserAvatar });
	const deleteAvatarMutation = useMutation({ mutationFn: deleteUserAvatar });

	const form = useForm({
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
		},
		onSubmit: async ({ value }) => {
			const { avatarFile, deleteAvatar, ...profile } = value;

			await updateSettingsMutation.mutateAsync(profile);
			if (avatarFile) {
				await updateAvatarMutation.mutateAsync(avatarFile);
			} else if (deleteAvatar) {
				await deleteAvatarMutation.mutateAsync();
			}

			await refreshMe(queryClient);
		},
	});

	return (
		<div>
			<h1 className="headerbar">Edit Settings</h1>
			<h2 className="headerbar">Profile</h2>
			<form
				id="profile-settings-form"
				onSubmit={(e) => {
					e.preventDefault();
					form.handleSubmit();
				}}
				className="hb-margined"
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
				<div id="edit_settings_avatar">
					<label htmlFor="edit_settings_avatar_file">Avatar</label>
					<div>
						<div id="edit_settings_avatar_disp">
							<img src={me?.avatar} alt="Your avatar" />
							<form.Field name="deleteAvatar">
								{(field) => (
									<div>
										<input
											id="edit_settings_avatar_delete"
											type="checkbox"
											checked={field.state.value}
											onChange={(e) => field.handleChange(e.target.checked)}
										/>
										<label htmlFor="edit_settings_avatar_delete">Delete avatar</label>
									</div>
								)}
							</form.Field>
						</div>
						<form.Field name="avatarFile">
							{(field) => (
								<input
									id="edit_settings_avatar_file"
									type="file"
									accept="image/*"
									onChange={(e) => field.handleChange(e.target.files?.[0] ?? undefined)}
								/>
							)}
						</form.Field>
						<p>
							Only images at least 150px by 150px will be accepted, with a maximum file
							size of 1MB.
						</p>
						<p>The images may be shrunk for GP use.</p>
					</div>
				</div>

				<form.Field name="pronouns">
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
				</form.Field>

				<form.Field name="birthday">
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
				</form.Field>

				<form.Field name="showAge">
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
				</form.Field>

				<form.Field name="location">
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
				</form.Field>

				<form.Field name="pmMail">
					{(field) => (
						<div>
							<div>Receive PM emails?</div>
							<div>
								<input
									id="edit_settings_pm_mail_yes"
									type="radio"
									name={field.name}
									checked={field.state.value === true}
									onChange={() => field.handleChange(true)}
								/>
								<label htmlFor="edit_settings_pm_mail_yes">Yes</label>
								<input
									id="edit_settings_pm_mail_no"
									type="radio"
									name={field.name}
									checked={field.state.value === false}
									onChange={() => field.handleChange(false)}
								/>
								<label htmlFor="edit_settings_pm_mail_no">No</label>
							</div>
						</div>
					)}
				</form.Field>

				<form.Field name="newGameMail">
					{(field) => (
						<div>
							<div>Receive new game emails?</div>
							<div>
								<input
									id="edit_settings_new_game_mail_yes"
									type="radio"
									name={field.name}
									checked={field.state.value === true}
									onChange={() => field.handleChange(true)}
								/>
								<label htmlFor="edit_settings_new_game_mail_yes">Yes</label>
								<input
									id="edit_settings_new_game_mail_no"
									type="radio"
									name={field.name}
									checked={field.state.value === false}
									onChange={() => field.handleChange(false)}
								/>
								<label htmlFor="edit_settings_new_game_mail_no">No</label>
							</div>
						</div>
					)}
				</form.Field>

				<form.Field name="gmMail">
					{(field) => (
						<div>
							<div>Receive GM emails?</div>
							<div>
								<input
									id="edit_settings_gm_mail_yes"
									type="radio"
									name={field.name}
									checked={field.state.value === true}
									onChange={() => field.handleChange(true)}
								/>
								<label htmlFor="edit_settings_gm_mail_yes">Yes</label>
								<input
									id="edit_settings_gm_mail_no"
									type="radio"
									name={field.name}
									checked={field.state.value === false}
									onChange={() => field.handleChange(false)}
								/>
								<label htmlFor="edit_settings_gm_mail_no">No</label>
							</div>
						</div>
					)}
				</form.Field>

				<form.Subscribe selector={(state) => state.canSubmit}>
					{(canSubmit) => (
						<div className="across-all-cols">
							<button type="submit" disabled={!canSubmit} className="trap-btn">
								Save
							</button>
						</div>
					)}
				</form.Subscribe>
			</form>
		</div>
	);
}
