import { useForm } from "@tanstack/react-form";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { FadeOut } from "#/components/FadeOut";
import { Select } from "#/components/Select";
import { UserAutocomplete, type UserRef } from "#/components/UserAutocomplete";
import { ApiError } from "#/lib/api";
import { requireAcpPermission } from "#/lib/auth-route";
import { useFlash } from "#/lib/use-flash";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	addUserToRole,
	createGrant,
	deleteGrant,
	deleteRole,
	type Effect,
	PROTECTED_ROLE_ID,
	PROTECTED_ROLE_MEMBER_ID,
	permissionsQueryOptions,
	removeUserFromRole,
	roleQueryOptions,
	updateGrant,
	updateRole,
} from "#/queries/rbac";
import styles from "./acp.module.css";

export const Route = createFileRoute("/acp/role/$roleId")({
	params: {
		parse: ({ roleId }) => ({ roleId: Number(roleId) }),
		stringify: ({ roleId }) => ({ roleId: String(roleId) }),
	},
	loader: async (opts) => {
		await requireAcpPermission("admin")(opts);
		const { context, params } = opts;
		await Promise.all([
			context.queryClient.ensureQueryData(roleQueryOptions(params.roleId)),
			context.queryClient.ensureQueryData(permissionsQueryOptions),
		]);
	},
	component: RouteComponent,
});

const EFFECT_OPTIONS: { value: Effect; label: string }[] = [
	{ value: "allow", label: "Allow" },
	{ value: "deny", label: "Deny" },
];

function errorList(exception: unknown): string[] {
	if (exception instanceof ApiError) return exception.errors.map((e) => e.detail);
	return ["Something went wrong."];
}

function RouteComponent() {
	const { roleId } = Route.useParams();
	const { data: role, refetch } = useSuspenseQuery(roleQueryOptions(roleId));
	const { data: permissions } = useSuspenseQuery(permissionsQueryOptions);
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const navigate = useNavigate();

	// Role #1 is hard-locked on the API (see rbac_repository.py): no rename,
	// re-owner, grant changes, or dropping its primary member. Mirror that here.
	const isProtected = roleId === PROTECTED_ROLE_ID;

	const [detailsErrors, setDetailsErrors] = useState<string[]>([]);
	const [detailsSaved, flashDetailsSaved] = useFlash();
	const [owner, setOwner] = useState<UserRef>({
		username: role.owner.username,
		id: role.owner.id,
	});
	const detailsForm = useForm({
		defaultValues: {
			name: role.name,
		},
		onSubmit: async ({ value }) => {
			setDetailsErrors([]);
			if (!owner.id) {
				setDetailsErrors(["An owner is required."]);
				return;
			}
			try {
				await updateRole(roleId, {
					name: value.name,
					owner_id: owner.id,
				});
				await refetch();
				flashDetailsSaved();
			} catch (exception) {
				setDetailsErrors(errorList(exception));
			}
		},
	});

	const [grantErrors, setGrantErrors] = useState<string[]>([]);
	const grantForm = useForm({
		defaultValues: {
			permission: permissions[0]?.value ?? "",
			scopeId: "",
			effect: "allow" as Effect,
		},
		onSubmit: async ({ value }) => {
			setGrantErrors([]);
			const permission = permissions.find((p) => p.value === value.permission);
			const globalOnly = !permission || permission.scopes.includes("global");
			const scopeType = globalOnly ? null : (permission?.scopes[0] ?? null);
			if (scopeType && !value.scopeId) {
				setGrantErrors(["A scope ID is required for this permission."]);
				return;
			}
			try {
				await createGrant(roleId, {
					permission: value.permission,
					scope_type: scopeType,
					scope_id: scopeType ? Number(value.scopeId) : null,
					effect: value.effect,
				});
				grantForm.reset();
				await refetch();
			} catch (exception) {
				setGrantErrors(errorList(exception));
			}
		},
	});

	const [grantRowError, setGrantRowError] = useState<string[]>([]);
	const changeGrantEffect = async (grantId: number, effect: Effect) => {
		setGrantRowError([]);
		try {
			await updateGrant(roleId, grantId, effect);
			await refetch();
		} catch (exception) {
			setGrantRowError(errorList(exception));
		}
	};
	const removeGrant = async (grantId: number) => {
		setGrantRowError([]);
		try {
			await deleteGrant(roleId, grantId);
			await refetch();
		} catch (exception) {
			setGrantRowError(errorList(exception));
		}
	};

	const [userErrors, setUserErrors] = useState<string[]>([]);
	const [newUser, setNewUser] = useState<UserRef>({ username: "", id: null });
	const [userFieldKey, setUserFieldKey] = useState(0);
	const addUser = async () => {
		if (!newUser.id) return;
		setUserErrors([]);
		try {
			await addUserToRole(roleId, newUser.id);
			setNewUser({ username: "", id: null });
			setUserFieldKey((key) => key + 1);
			await refetch();
		} catch (exception) {
			setUserErrors(errorList(exception));
		}
	};
	const removeUser = async (userId: number) => {
		setUserErrors([]);
		try {
			await removeUserFromRole(roleId, userId);
			await refetch();
		} catch (exception) {
			setUserErrors(errorList(exception));
		}
	};

	const [confirmingDelete, setConfirmingDelete] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const [deleteErrors, setDeleteErrors] = useState<string[]>([]);
	const confirmDelete = async () => {
		setDeleteErrors([]);
		setDeleting(true);
		try {
			await deleteRole(roleId);
			await navigate({ to: "/acp/rbac" });
		} catch (exception) {
			setDeleteErrors(errorList(exception));
			setDeleting(false);
		}
	};

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				{role.name}
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{detailsErrors.length > 0 && (
					<div className="banner error-banner">
						<ul>
							{detailsErrors.map((error) => (
								<li key={error}>{error}</li>
							))}
						</ul>
					</div>
				)}
				<form
					className={styles["role-form"]}
					onSubmit={(e) => {
						e.preventDefault();
						detailsForm.handleSubmit();
					}}
				>
					<detailsForm.Field name="name">
						{(field) => (
							<div>
								<label htmlFor={field.name}>Name</label>
								<input
									id={field.name}
									name={field.name}
									type="text"
									maxLength={48}
									value={field.state.value}
									disabled={isProtected}
									onBlur={field.handleBlur}
									onChange={(e) => field.handleChange(e.target.value)}
								/>
							</div>
						)}
					</detailsForm.Field>
					{isProtected ? (
						<div>
							<label htmlFor="role-owner">Owner</label>
							<input id="role-owner" type="text" value={role.owner.username} disabled />
						</div>
					) : (
						<UserAutocomplete
							id="role-owner"
							label="Owner"
							defaultUsername={role.owner.username}
							onChange={setOwner}
						/>
					)}
					{!isProtected && (
						<div className={styles["save-row"]}>
							<detailsForm.Subscribe selector={(state) => state.isSubmitting}>
								{(isSubmitting) => (
									<button type="submit" className="skew-btn" disabled={isSubmitting}>
										Save
									</button>
								)}
							</detailsForm.Subscribe>
							<FadeOut active={detailsSaved}>Saved</FadeOut>
						</div>
					)}
				</form>

				<section className={styles["role-section"]}>
					<h3>Grants</h3>
					{grantRowError.length > 0 && (
						<div className="banner error-banner">
							<ul>
								{grantRowError.map((error) => (
									<li key={error}>{error}</li>
								))}
							</ul>
						</div>
					)}
					{role.grants.length === 0 ? (
						<p>No grants.</p>
					) : (
						<ul className={styles["entity-list"]}>
							{role.grants.map((grant) => (
								<li key={grant.id}>
									<span>{grant.description ?? grant.permission.label}</span>
									{isProtected ? (
										<span>{grant.effect}</span>
									) : (
										<>
											<Select
												id={`grant-effect-${grant.id}`}
												items={EFFECT_OPTIONS}
												getId={(option) => option.value}
												getLabel={(option) => option.label}
												selectedId={grant.effect}
												onChange={(value) =>
													changeGrantEffect(grant.id, value as Effect)
												}
											/>
											<button type="button" onClick={() => removeGrant(grant.id)}>
												Remove
											</button>
										</>
									)}
								</li>
							))}
						</ul>
					)}

					{!isProtected && (
						<>
							{grantErrors.length > 0 && (
								<div className="banner error-banner">
									<ul>
										{grantErrors.map((error) => (
											<li key={error}>{error}</li>
										))}
									</ul>
								</div>
							)}
							<form
								className={styles["role-form"]}
								onSubmit={(e) => {
									e.preventDefault();
									grantForm.handleSubmit();
								}}
							>
								<grantForm.Field name="permission">
									{(field) => (
										<div>
											<label htmlFor="grant-permission">Permission</label>
											<Select
												id="grant-permission"
												items={permissions}
												getId={(permission) => permission.value}
												getLabel={(permission) => permission.label}
												selectedId={field.state.value}
												onChange={(value) => field.handleChange(value)}
											/>
										</div>
									)}
								</grantForm.Field>

								<grantForm.Subscribe selector={(state) => state.values.permission}>
									{(permissionValue) => {
										const permission = permissions.find(
											(candidate) => candidate.value === permissionValue,
										);
										const globalOnly =
											!permission || permission.scopes.includes("global");
										const scopeType = globalOnly
											? "global"
											: (permission?.scopes[0] ?? "");
										return (
											<>
												<div>
													<label htmlFor="grant-scope-type">Scope type</label>
													<input
														id="grant-scope-type"
														type="text"
														value={scopeType}
														disabled
													/>
												</div>
												<grantForm.Field name="scopeId">
													{(field) => (
														<div>
															<label htmlFor="grant-scope-id">Scope ID</label>
															<input
																id="grant-scope-id"
																type="number"
																min={0}
																value={field.state.value}
																disabled={globalOnly}
																onChange={(e) => field.handleChange(e.target.value)}
															/>
														</div>
													)}
												</grantForm.Field>
											</>
										);
									}}
								</grantForm.Subscribe>

								<grantForm.Field name="effect">
									{(field) => (
										<div>
											<label htmlFor="grant-effect">Effect</label>
											<Select
												id="grant-effect"
												items={EFFECT_OPTIONS}
												getId={(option) => option.value}
												getLabel={(option) => option.label}
												selectedId={field.state.value}
												onChange={(value) => field.handleChange(value as Effect)}
											/>
										</div>
									)}
								</grantForm.Field>

								<grantForm.Subscribe selector={(state) => state.isSubmitting}>
									{(isSubmitting) => (
										<button type="submit" className="skew-btn" disabled={isSubmitting}>
											Add grant
										</button>
									)}
								</grantForm.Subscribe>
							</form>
						</>
					)}
				</section>

				<section className={styles["role-section"]}>
					<h3>Users</h3>
					{userErrors.length > 0 && (
						<div className="banner error-banner">
							<ul>
								{userErrors.map((error) => (
									<li key={error}>{error}</li>
								))}
							</ul>
						</div>
					)}
					{role.users.length === 0 ? (
						<p>No users.</p>
					) : (
						<ul className={styles["entity-list"]}>
							{role.users.map((member) => (
								<li key={member.id}>
									<span>{member.username}</span>
									{!(isProtected && member.id === PROTECTED_ROLE_MEMBER_ID) && (
										<button type="button" onClick={() => removeUser(member.id)}>
											Remove
										</button>
									)}
								</li>
							))}
						</ul>
					)}

					<form
						className={styles["role-form"]}
						onSubmit={(e) => {
							e.preventDefault();
							addUser();
						}}
					>
						<UserAutocomplete
							key={userFieldKey}
							id="add-user-combo"
							label="Add user"
							onChange={setNewUser}
							exclude={(user) => role.users.some((member) => member.id === user.id)}
						/>
						<button type="submit" className="skew-btn" disabled={!newUser.id}>
							Add
						</button>
					</form>
				</section>

				{!isProtected && (
					<section className={styles["role-section"]}>
						<h3>Delete role</h3>
						{deleteErrors.length > 0 && (
							<div className="banner error-banner">
								<ul>
									{deleteErrors.map((error) => (
										<li key={error}>{error}</li>
									))}
								</ul>
							</div>
						)}
						{confirmingDelete ? (
							<>
								<p>This will permanently delete this role. This cannot be undone.</p>
								<div className={styles["role-form"]}>
									<button
										type="button"
										className="skew-btn"
										onClick={confirmDelete}
										disabled={deleting}
									>
										Confirm
									</button>
									<button
										type="button"
										onClick={() => setConfirmingDelete(false)}
										disabled={deleting}
									>
										Cancel
									</button>
								</div>
							</>
						) : (
							<button type="button" onClick={() => setConfirmingDelete(true)}>
								Delete role
							</button>
						)}
					</section>
				)}
			</div>
		</div>
	);
}
